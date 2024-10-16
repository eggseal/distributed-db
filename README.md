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
   python -m grpc_tools.protoc -I. --python_out=./bin --grpc_python_out=./bin ./message.proto
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
   python -m grpc_tools.protoc -I. --python_out=./bin --grpc_python_out=./bin ./message.proto
   ```
1. Crea los enlaces simbolicos para cada proceso en un proceso de Command Prompt con permisos de administrador
   ```batch
   mklink /H "./node/message_pb2.py" "./bin/message_pb2.py"
   mklink /H "./node/message_pb2_grpc.py" "./bin/message_pb2_grpc.py"
   mklink /H "./proxy/message_pb2.py" "./bin/message_pb2.py"
   mklink /H "./proxy/message_pb2_grpc.py" "./bin/message_pb2_grpc.py"
   ```

## Uso

Ejecute siempre el Proxy antes que los Node por favor y gracias.

Para el proxy:
```
python proxy/proxy.py
```
Para los nodos
```
python node/node.py -proxy <address> -address <address> -filename <name.extension>
```
Donde `address` son direcciones que incluyen IP/dominio y puerto de la forma `domain:port` y `name.extension` es un nombre de archivo con extension seguida de un punto

`-proxy` es la direccion donde de esta ejecutando el proxy

`-address` es la direccion de el nodo que se va a ejectutar

`-filename` el nombre del arhcivo que se va a manejar

Para el cliente
```
python client/client.py -h <ip> -p <port> --cmd <cmd>
```

`ip` es la ip o dominio del proxy

`port` el puerto del proxy

`cmd` es un comando del tipo `/write <index> "<message>"` o `/read <index>`