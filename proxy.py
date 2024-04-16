import sys, os, time, socket, select

cache_dir = os.path.dirname(os.path.realpath(__file__))

if not os.path.exists(cache_dir):
    os.makedirs(cache_dir)

def cache_response(res, file):
    cache_path = os.path.join(cache_dir, file)
    with open(cache_path, 'wb') as cache_file:
        cache_file.write(res)

def forward_request(msg):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    # Split the request into lines
    try:
        parsed_msg =  msg.split("\r\n")
        request = parsed_msg[0]
        method, path, http_version = request.split(" ")
        filename_to_cache = path_to_filename(path)

        new_path = "/" + '/'.join(path.split('/')[2:])
        new_req = f"{method} {new_path} {http_version}"
        server_address = path.split('/')[1]
        new_host = "Host: " + server_address
        
        print("server address ->  " + server_address)

        if ('www' in server_address):
            new_request = [new_req, new_host, "Connection: close"]
            for msg in parsed_msg[2:]:
                    if not msg.startswith("Connection:"):
                        new_request.append(msg)

            http_req = '\r\n'.join(new_request).encode('utf-8')
            sock.connect((server_address, 80))

            sock.sendall(http_req)
            
            res = b""

            while True:
                
                data = sock.recv(4096)
                if not data:
                    break
                res += data
            
            cache_response(res, filename_to_cache)

            print(res)
            return res
        else:
            return None
    finally:
        sock.close()

def path_to_filename(path):
    filename = ""
    for char in path[1:]:
        if char.lower() in "?.%/~":
            filename += '_'
        else:
            filename += char
    
    return filename[:255]

def file_is_cached(file):
    file_path = os.path.join(cache_dir, file)
    
    return os.path.exists(file_path)

def get_cached_data(file):
    file_path = os.path.join(cache_dir, file)
    
    if not os.path.exists(file_path):
        return None
    
    with open(file_path, 'rb') as f: 
        data = f.read()
    
    print("returning cached data instead of sending a http request for " + file_path)
    return data

def cache_not_expired(filename):
    filepath = os.path.join(cache_dir, filename)
    if not (time.time() - os.path.getmtime(filepath) < max_age):
        print("cache has expired for " + filename)
    return time.time() - os.path.getmtime(filepath) < max_age


def handle_request(data):

    decoded_msg = data.decode('utf-8')

    parsed_msg =  decoded_msg.split("\r\n")
    request = parsed_msg[0]
    path = request.split(" ")[1]
    filename = path_to_filename(path)

    if file_is_cached(filename) and cache_not_expired(filename):
        return get_cached_data(filename)
    
    return forward_request(decoded_msg)


if __name__ == "__main__":

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    max_age = int(sys.argv[1])
    server_address = ('localhost', 8888)
    print('starting up on {} port {}'.format(*server_address))
    sock.bind(server_address)
    sock.listen(1)

    inputs = [sock]
    outputs = []
    sockets_data = {}

    while inputs:
        readable, writable, exceptional = select.select(inputs, outputs, inputs)

        for s in readable:
            if s is sock:
                connection, client_address = s.accept()
                connection.setblocking(0)
                inputs.append(connection)
                sockets_data[connection] = b""
            else:
                data = s.recv(4096)
                if data:
                    sockets_data[s] += data

                    if b"\r\n\r\n" in data:
                        # print(data)
                        res = handle_request(sockets_data[s])
                        # res = forward_request(sockets_data[s])
                        if res:
                            s.sendall(res)
                        sockets_data[s] = b""
                else:
                    inputs.remove(s)
                    sockets_data.pop(s, None)
                    s.close()
