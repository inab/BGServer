# Heavy-lifting background server library

This library has been designed to delegate long, heavy-lifting background jobs into a server. The server is created on demand, and the program using it communicates with the server using a UNIX socket. The communication protocol on both ways is:

| Byte | Var | Dword | Var |
| --- | --- | --- | --- |
| `Label` length | `Label` | `Payload` length | `Payload` |

The messages follow next rules:

* `Label` length is 1 byte, so labels cannot be longer than 255.

* `Label` is, by default UTF-8 encoded.

* When there is no label, the label length must be 0.

* `Payload` length is an unsigned integer, using 4 bytes in big endian.

* `Payload` is, by default UTF-8 encoded JSON, so clients in other programming languages can encode/decode it.

* When there is no payload, the payload length must be 0.

## Library usage

```python
class TestStreamRequestHandler(BGRequestHandler):
	def handleRequest(self,label,payload):
		with open("/tmp/testlog.txt",mode="a",encoding="utf-8") as l:
			l.write(str(time.time())+"\n")
			import json
			json.dump(self.server.config,l)
		
		# And sending the example
		return "ECHO",{"label": label, "payload": payload}


setupBlock = {
	"server": {
		"lock": "/tmp/bgserver.lock",
		"socket": "/tmp/bgserver.socket",
	}
}

# Create the instance which will help
bgServer = BGServer(setupBlock,handlerClass=TestStreamRequestHandler)
```

The initialization accepts a dictionary, where the keys `.server.lock` and `server.socket` are honoured when
the used lock file and UNIX socket are created. Therefore, their paths must be in an existing, writable directory.

```python
rLabel , rPayload = bgServer.talkServer("A Label",{"payload": ...})
```

Each time a client wants to send a message to the background server, the `talkServer` method is used. It returns the
label and the payload sent by the server. If there is no background server just running (or it died) for the heavy
lifting tasks, it is created.
