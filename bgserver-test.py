#!/usr/bin/env python3

import sys
import socketserver
import time

from BGServer.bgserver import BGServer , BGRequestHandler


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

rLabel , rPayload = bgServer.talkServer("COViD19",{"cinco": ["lobitos",time.time(),True,{"tiene": "la loba","fin":None }]},stderr=sys.stderr)

import json
print("ANSWER: {}\n\n{}\n".format(rLabel,json.dumps(rPayload)))
