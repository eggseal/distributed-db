# Multithreading
import threading
from concurrent import futures
from queue import Queue
from multiprocessing import Semaphore, Lock
# General
import sys, os, time
import logging as console
# gRPC
import grpc, message_pb2, message_pb2_grpc

FORMAT = '[%(asctime)s][%(levelname)s]::%(name)s >> %(message)s'
DATEFMT = '%H:%M:%S'

leader = False
leader_address = ""
heartbeat_lock = Lock()
heartcheck_lock = Lock()
heartupdate_semaphore = Semaphore(1)
last_heartbeat = 0
nodes = Queue()

class NodeServicer(message_pb2_grpc.NodeServicer):
    path: str
    address: str

    def __init__(self, path: str, address: str) -> None:
        self.path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', path)
        self.address = address
        try:
            open(self.path, 'x')
        except FileExistsError:
            pass
        console.info(f'Node servicer using file path: {self.path} on address: {self.address}')

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
        
        console.info(f'Am I leader? {leader}')
        if leader:
            console.info(list(nodes.queue))
            req = message_pb2.WriteLineRequest(line=line, content=content)
            for address in list(nodes.queue):
                if address == self.address: continue
                with grpc.insecure_channel(address) as channel:
                    stub = message_pb2_grpc.NodeStub(channel)
                    stub.write_line(req)
        return message_pb2.WriteLineResponse(success=True)

    def update_list(self, request, context):
        address = request.address

        if address not in list(nodes.queue):
            nodes.put(address)
        return message_pb2.RegisterNodeResponse(registered=True, leader=False, leader_address=self.address)
    
    def signal_heartbeat(self, request, context):
        global last_heartbeat

        heartupdate_semaphore.acquire()
        last_heartbeat = time.time()
        heartupdate_semaphore.release()

        console.info('Received hearbeat from leader')
        return message_pb2.Empty()

def register_node(proxy: str, address: str, retries=3, delay=5):
    global leader_address
    for attempt in range(retries):
        try:
            with grpc.insecure_channel(proxy) as channel:
                stub = message_pb2_grpc.ProxyStub(channel)
                req = message_pb2.RegisterNodeRequest(address=address)
                res = stub.register_node(req)
            if not res.leader:
                leader_address = res.leader_address
            if res.registered:
                return res.leader
            else:
                raise Exception("Failed registering with proxy")
        except Exception as e:
            console.error(f"Attempt {attempt+1}/{retries} failed: {e}")
            if attempt < retries - 1:
                time.sleep(delay)
    console.error(f"Failed to register node after {retries} attempts")
    exit(1)

def signal_dead_leader():
    console.warning('Leader is dead')
    pass

def start_heartbeat(add):
    req = message_pb2.Empty()
    while True:
        if not leader: heartbeat_lock.acquire()
        for address in list(nodes.queue):
            if address == add: continue
            with grpc.insecure_channel(address) as channel:
                stub = message_pb2_grpc.NodeStub(channel)
                stub.signal_heartbeat(req)
        time.sleep(1)

def detect_heartbeat():
    while True:
        if leader: heartcheck_lock.acquire()
        heartupdate_semaphore.acquire()
        if time.time() - last_heartbeat >= 3:
            heartupdate_semaphore.release()
            signal_dead_leader()
        else:
            heartupdate_semaphore.release()
        time.sleep(1)

def serve_grpc(address: str, filepath: str):
    add_p = address.split(':')[1]

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    message_pb2_grpc.add_NodeServicer_to_server(NodeServicer(filepath, address), server)
    server.add_insecure_port(f'[::]:{add_p}')
    console.info(f"gRPC server started on port {add_p}")
    server.start()
    server.wait_for_termination()
        
# python node.py -proxy 127.0.0.1:50051 -p 50052 -filename "a file"  
def main(argc: int, argv: list[str]):
    global leader
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

    leader = register_node(proxy, address)
    create_beat = threading.Thread(target=start_heartbeat, args=[address])
    detect_beat = threading.Thread(target=detect_heartbeat)

    create_beat.start()
    detect_beat.start()
    serve_grpc(address, file)

    create_beat.join()
    detect_beat.join()

if __name__ == "__main__":
    console.basicConfig(level=console.INFO, handlers=[console.StreamHandler()], format=FORMAT, datefmt=DATEFMT)
    main(len(sys.argv), sys.argv)