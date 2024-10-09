# Proyecto 1: Distributed Database

## Configuración

### Linux/MacOS

1. Crea y activa el ambiente virtual de Python que vas a usar

   1. Con Anaconda
      ```sh
      conda create --yes --name distributed-db python=3.11
      conda activate distributed-db
      ```
   1. Con Python
      ```sh
      python -m venv distributed-db
      source distributed-db/bin/activate
      ```

1. Instala las librerias requeridas
   ```sh
   pip install -r ./requirements.txt
   ```
1. Compila el archivo de protocolo
   ```sh
   python -m grpcio-tools.protoc -I. --python_out=. --grpc_python_out=. ./message.proto
   ```
1. Crea los enlaces simbolicos para cada proceso
   ```sh
   ln "./message_pb2.py" "./node/message_pb2.py"
   ln "./message_pb2_grpc.py" "./node/message_pb2_grpc.py"
   ln "./message_pb2.py" "./proxy/message_pb2.py"
   ln "./message_pb2_grpc.py" "./proxy/message_pb2_grpc.py"
   ```

### Windows

1. Crea y activa el ambiente virtual de Python que vas a usar

   1. Con Anaconda
      ```batch
      conda create --yes --name distributed-db python=3.11
      conda activate distributed-db
      ```
   1. Con Python
      ```batch
      python -m venv distributed-db
      .\distributed-db\Scripts\activate.bat
      ```

1. Instala las librerias requeridas
   ```batch
   pip install -r .\requirements.txt
   ```
1. Compila el archivo de protocolo
   ```batch
   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. message.proto
   python -m grpc_tools.protoc -I. --python_out=./bin --grpc_python_out=./bin ./message.proto
   ```
1. Crea los enlaces simbolicos para cada proceso en un proceso de Command Prompt con permisos de administrador
   ```batch
   mklink /H "./node/message_pb2.py" "./bin/message_pb2.py"
   mklink /H "./node/message_pb2_grpc.py" "./bin/message_pb2_grpc.py"
   mklink /H "./proxy/message_pb2.py" "./bin/message_pb2.py"
   mklink /H "./proxy/message_pb2_grpc.py" "./bin/message_pb2_grpc.py"
   ```
