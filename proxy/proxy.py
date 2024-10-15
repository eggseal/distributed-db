# HTTP
from flask import Flask, request
# Multithreading
from concurrent import futures
from threading import Thread
from queue import Queue
# General
import sys, os
import logging as console
# gRPC
import grpc, message_pb2, message_pb2_grpc

OK = 200
BAD_REQUEST = 400
NOT_FOUND = 404
SERVICE_UNAVAILABLE = 503

FORMAT = '[%(asctime)s][%(levelname)s]::%(name)s >> %(message)s'
DATEFMT = '%H:%M:%S'

app = Flask(__name__)

# Initialize thread-safe queue for nodes
nodes = Queue()
leader = -1

def rr_skip_generator(q: Queue, skip: int):
    i = 0
    list_copy = list(q.queue)  # Access a copy of the queue safely
    while True:
        if not list_copy: 
            yield None
        elif i == skip and len(list_copy) != 1:
            i = (i + 1) % len(list_copy)
        else:
            yield list_copy[i]
            i = (i + 1) % len(list_copy)

node_gen = rr_skip_generator(nodes, leader)
def next_node() -> str | None:
    if nodes.empty():
        return None
    return next(node_gen)

class ProxyServicer(message_pb2_grpc.ProxyServicer):
    def register_node(self, request, context):
        global leader
        address = request.address
        console.info(f"Received registration from {address}")
        is_registered = False
        is_leader = False

        # Add the node to the queue if it doesn't already exist
        if address not in list(nodes.queue):  # Safely convert queue to list for comparison
            nodes.put(address)
        is_registered = True
        # If there were no nodes, force this one as the leader
        console.info(f'Leader index: {leader}')
        if leader == -1:
            leader = 0  # The first node becomes the leader
            is_leader = True
        else:
            console.info(f'Leader address: {list(nodes.queue)[leader]}')
            try:
                with grpc.insecure_channel(list(nodes.queue)[leader]) as channel:
                    stub = message_pb2_grpc.NodeStub(channel)
                    req = message_pb2.RegisterNodeRequest(address=address)
                    res = stub.update_list(req)
                console.info(f'Leader node update success={res.registered}')
            except:
                leader = list(nodes.queue).index(address)
                is_leader = True
        console.info(f"Current nodes: {list(nodes.queue)}")  # Print a safe copy of the queue
        return message_pb2.RegisterNodeResponse(registered=is_registered, leader=is_leader, leader_address = list(nodes.queue)[leader])
    
    def declare_leader(self, request, context):
        global leader
        address = request.address
        # Declare the new leader
        try:
            leader = list(nodes.queue).index(address)
        except ValueError:
            console.error(f"Node {address} not found in the node list.")
            return message_pb2.DeclareLeaderResponse(addresses=list())
        return message_pb2.DeclareLeaderResponse(addresses=list(nodes))
    
@app.route('/', methods=['GET'])
def handle_read():
    data = request.get_json()
    try:
        index = int(data.get('index'))
    except:
        return { 'status': BAD_REQUEST }, BAD_REQUEST

    node = next_node()
    console.info(f"Current nodes: {list(nodes.queue)}") 
    if node is None:
        return { 'status': SERVICE_UNAVAILABLE }, SERVICE_UNAVAILABLE
    
    with grpc.insecure_channel(node) as channel:
        stub = message_pb2_grpc.NodeStub(channel)
        req = message_pb2.ReadLineRequest(line=index)
        res = stub.read_line(req)

    status = OK if res.success else NOT_FOUND
    return { 'status': status, 'content': res.content }, status

@app.route('/', methods=['POST'])
def handle_write():
    data = request.get_json()
    try:
        index = int(data.get('index'))
        message = data.get('message')
        
        if not isinstance(index, int) or not isinstance(message, str):
            raise ValueError("Invalid input data.")
    except (ValueError, TypeError) as e:
        console.error(f"Invalid request: {e}")
        return { 'status': BAD_REQUEST }, BAD_REQUEST

    node = list(nodes.queue)[leader] or None
    console.info(f"Current leader: {leader}") 
    if node is None:
        return { 'status': SERVICE_UNAVAILABLE }, SERVICE_UNAVAILABLE
    
    with grpc.insecure_channel(node) as channel:
        stub = message_pb2_grpc.NodeStub(channel)
        req = message_pb2.WriteLineRequest(line=index, content=message)
        res = stub.write_line(req)

    status = OK if res.success else BAD_REQUEST
    return { 'status': status }, status


def serve_grpc(port: int):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    message_pb2_grpc.add_ProxyServicer_to_server(ProxyServicer(), server)
    server.add_insecure_port(f'[::]:{port}')
    console.info(f"gRPC server started on port {port}")
    server.start()
    server.wait_for_termination()

def serve_http(port: int):
    app.run('0.0.0.0', port=port, debug=False)

def main(argc: int, argv: list[str]):
    grpc_p = int(argv[argv.index('-grpc') + 1]) if '-grpc' in argv else 50050
    http_p = int(argv[argv.index('-http') + 1]) if '-http' in argv else 5000
    console.info(f'Using ports HTTP={http_p}, GRPC={grpc_p}')

    if not os.getenv('STARTED', ""):
        grpc_thread = Thread(target=serve_grpc, args=[grpc_p])
        grpc_thread.start()
        os.environ['STARTED'] = "1"

    serve_http(http_p)
    if 'grpc_thread' in locals():
        grpc_thread.join()

if __name__ == '__main__':
    console.basicConfig(level=console.INFO, handlers=[console.StreamHandler()], format=FORMAT, datefmt=DATEFMT)
    main(len(sys.argv), sys.argv)
