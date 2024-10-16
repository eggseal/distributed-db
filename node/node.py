# Multithreading
import threading
from concurrent import futures
from queue import Queue
# General
import sys, os, time
import logging as console
# gRPC
import grpc, message_pb2, message_pb2_grpc
import grpc._server

FORMAT = '[%(asctime)s][%(levelname)s]::%(name)s >> %(message)s'
DATEFMT = '%H:%M:%S'

# Raft states
FOLLOWER = "follower"
CANDIDATE = "candidate"
LEADER = "leader"

nodes = Queue()

class NodeServicer(message_pb2_grpc.NodeServicer):
    path: str
    address: str
    term: int
    state: str
    votes: int
    last_heartbeat: float
    leader_address: str

    def __init__(self, path: str, address: str) -> None:
        self.path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', path)
        self.address = address
        try:
            open(self.path, 'x')
        except FileExistsError:
            pass

        self.term = 0
        self.state = FOLLOWER
        self.votes = 0
        self.last_heartbeat = time.time()
        self.leader_address = ""
        console.info(f'Node servicer using file path: {self.path} on address: {self.address}')

    # Raft heartbeat
    def append_entries(self, request, context):
        self.last_heartbeat = time.time()
        self.state = FOLLOWER
        return message_pb2.Empty()

    def request_vote(self, request, context):
        candidate_term = request.term
        if candidate_term > self.term:
            self.term = candidate_term
            self.state = FOLLOWER
            return message_pb2.VoteResponse(vote_granted=True, term=self.term)
        else:
            return message_pb2.VoteResponse(vote_granted=False, term=self.term)

    def read_line(self, request, context):
        line = request.line
        try:
            with open(self.path, 'r') as file:
                lines = file.readlines()
            if len(lines) <= line or line < 0:
                return message_pb2.ReadLineResponse(content='Line not found', success=False)
            return message_pb2.ReadLineResponse(content=lines[line].strip(), success=True)
        except FileNotFoundError:
            console.error(f"File not found: {self.path}")
            return message_pb2.ReadLineResponse(content='File not found', success=False)
        except Exception as e:
            console.error(f"Error reading file: {e}")
            return message_pb2.ReadLineResponse(content='Error reading file', success=False)

    def write_line(self, request, context):
        line = request.line
        content = request.content

        with open(self.path, 'r+') as file:
            lines = file.readlines()
            while len(lines) <= line:
                lines.append('\n')
            lines[line] = f'{content}\n'
            file.seek(0)
            file.writelines(lines)
        
        # Propagate writes if leader
        if self.state == LEADER:
            for node_address in list(nodes.queue):
                if node_address == self.address: continue
                with grpc.insecure_channel(node_address) as channel:
                    stub = message_pb2_grpc.NodeStub(channel)
                    stub.write_line(request)
        return message_pb2.WriteLineResponse(success=True)

    def update_list(self, request, context):
        address = request.address

        if address not in list(nodes.queue):
            nodes.put(address)
        return message_pb2.RegisterNodeResponse(registered=True, leader=False, leader_address=self.address)
    
    def confirm_alive(self, request, context):
        return message_pb2.Empty()

# Raft Leader Election Logic
def start_election(node: NodeServicer, proxy_address: str):
    node.state = CANDIDATE
    node.term += 1
    node.votes = 1  # Vote for itself
    console.info(f'Starting election. Term={node.term}')

    for node_address in list(nodes.queue):
        if node_address == node.address:
            continue
        with grpc.insecure_channel(node_address) as channel:
            stub = message_pb2_grpc.NodeStub(channel)
            request = message_pb2.VoteRequest(candidate_address=node.address, term=node.term)
            try:
                response = stub.request_vote(request)
                if response.vote_granted:
                    node.votes += 1
            except grpc.RpcError:
                console.error(f"Failed to contact node {node_address}")

    # If this node wins the majority of votes, it becomes the leader
    if node.votes > (nodes.qsize() // 2):
        console.info(f'{node.address} is elected leader for term {node.term}')
        node.state = LEADER
        node.leader_address = node.address

        with grpc.insecure_channel(proxy_address) as channel:
            stub = message_pb2_grpc.ProxyStub(channel)
            req = message_pb2.RegisterNodeRequest(address=node.address)
            res = stub.declare_leader(req)
            console.info(res.addresses)
            for address in res.addresses:
                if address in list(nodes.queue) or address == node.address: continue
                nodes.put(address)

def check_heartbeat(node: NodeServicer, proxy_address: str):
    while True:
        if node.state == LEADER:
            for node_address in list(nodes.queue):
                if node_address == node.address: continue
                with grpc.insecure_channel(node_address) as channel:
                    stub = message_pb2_grpc.NodeStub(channel)
                    req = message_pb2.Empty()
                    try:
                        stub.append_entries(req)
                    except:
                        pass
            continue
        if node.state != LEADER and time.time() - node.last_heartbeat > 3:
            start_election(node, proxy_address)
        console.info(node.last_heartbeat)
        time.sleep(1)

def register_with_proxy(proxy_address: str, node_address: str):
    with grpc.insecure_channel(proxy_address) as channel:
        stub = message_pb2_grpc.ProxyStub(channel)
        request = message_pb2.RegisterNodeRequest(address=node_address)
        response = stub.register_node(request)
        console.info(f"Registered with proxy. Leader: {response.leader_address}")
        if response.leader_address:
            nodes.put(response.leader_address)

def serve_grpc(address: str, filepath: str) -> tuple[grpc._server._Server, NodeServicer]:
    add_p = address.split(':')[1]

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    node_servicer = NodeServicer(filepath, address)
    message_pb2_grpc.add_NodeServicer_to_server(node_servicer, server)
    server.add_insecure_port(f'[::]:{add_p}')
    console.info(f"gRPC server started on port {add_p}")
    return (server, node_servicer)
    
def main(argc: int, argv: list[str]):
    try:
        proxy = argv[argv.index('-proxy') + 1]
        address = argv[argv.index('-address') + 1]
    except Exception as e:
        console.error(e)
        console.error('Exaple usage: python [...]node.py -proxy <domain>:<port> -address <domain>:<port> -filename "<name_with_extension>"')
        exit(1)
    try: file = argv[argv.index('-filename') + 1]
    except: file = "file.txt"
    console.info(f'Using address GRPC={address}, Connecting to proxy={proxy}, Using file=./resources/{file}')

    register_with_proxy(proxy, address)
    server, node_servicer = serve_grpc(address, file)

    heartbeat_thread = threading.Thread(target=check_heartbeat, args=[node_servicer, proxy])
    heartbeat_thread.start()
    server.start()
    server.wait_for_termination()
    heartbeat_thread.join()

if __name__ == "__main__":
    console.basicConfig(level=console.INFO, handlers=[console.StreamHandler()], format=FORMAT, datefmt=DATEFMT)
    main(len(sys.argv), sys.argv)