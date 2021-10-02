#!/usr/bin/env python3

import os
import tempfile
import socket
import socketserver

import time
import daemon
import sys
from RWFileLock import RWFileLock, LockError

import json
import struct

class BGRequestHandler(socketserver.BaseRequestHandler):
	ZERO_PACK = struct.pack("!I",0)
	SOCKET_READ_SIZE = 4096
	
	def handleRequest(self,label,payload):
		"""
		This method is the one to be reimplemented by subclasses, so
		the implementations do not have to bother with the unmarshalling
		and marshalling tasks
		"""
		# By default, echo
		return label, payload
	
	def handle(self):
		# Receiving what you want
		label , payload = self.RecvMessage(self.request)
		
		rLabel, rPayload = self.handleRequest(label,payload)
		
		# And sending the example
		self.SendMessage(self.request,rLabel,rPayload)
	
	@classmethod
	def SendMessage(cls,sock,label,payload):
		bLabel = bytes(label,"utf-8")
		bLabelSize = bytes([len(bLabel)])
		
		# Sending the label and the payload
		sock.sendall(bLabelSize)
		if len(bLabel) > 0:
			sock.sendall(bLabel)
		
		if(payload is not None):
			bPayload = bytes(json.dumps(payload),"utf-8")
			bPayloadSize = struct.pack("!I",len(bPayload))
			
			sock.sendall(bPayloadSize)
			sock.sendall(bPayload)
		else:
			sock.sendall(cls.ZERO_PACK)
	
	@classmethod
	def RecvBytes(cls,sock,rSize,received=None):
		fSize = rSize
		rBytes = b''
		
		l_received = 0  if received is None  else  len(received)
		while fSize > 0:
			# Is the buffer empty?
			if l_received == 0:
				received = sock.recv(cls.SOCKET_READ_SIZE)
				l_received = len(received)
			
			if l_received > fSize:
				pRBytes = received[0:fSize]
				received = received[fSize:]
				l_received -= fSize
				fSize = 0
			else:
				pRBytes = received
				received = None
				fSize -= l_received
				l_received = 0
			rBytes += pRBytes
		
		# When should we return?
		return rBytes,received
	
	@classmethod
	def RecvMessage(cls,sock):
		rLabel = ''
		rPayload = None
		
		rLabelSizeB , received = cls.RecvBytes(sock,1)
		rLabelSize = rLabelSizeB[0]
		# Decoding the label
		if rLabelSize > 0:
			bRLabel , received = cls.RecvBytes(sock,rLabelSize,received)
			rLabel = str(bRLabel,"utf-8")
		
		# An int is 4 bytes
		bRPayloadSize , received = cls.RecvBytes(sock,4,received)
		(rPayloadSize,) = struct.unpack("!I",bRPayloadSize)
		# Decoding the payload
		if rPayloadSize > 0:
			bRPayload, received = cls.RecvBytes(sock,rPayloadSize,received)
			rPayload = json.loads(str(bRPayload,"utf-8"))
			
		# TODO: if received has contents, complain?
		
		return rLabel , rPayload

class BGServer(object):
	DEFAULT_SOCKET_NAME = "bgserver.sock"
	DEFAULT_LOCK_FILENAME = "bgserver.lock"
	
	def __init__(self,config,handlerClass=BGRequestHandler):
		self.config = config
		
		if not issubclass(handlerClass,BGRequestHandler):
			raise TypeError("Handler class must be a subclass of " + BGRequestHandler.__name__)
		
		self.handlerClass = handlerClass
		
		# Initializing this
		self.serverLockFile = self.config.get('server',{}).get('lock')
		if self.serverLockFile is None:
			self.serverLockFile = os.path.join(tempfile.gettempdir(),self.DEFAULT_LOCK_FILENAME)
		
		self.serverSocket = self.config.get('server',{}).get('socket')
		if self.serverSocket is None:
			self.serverSocket = os.path.join(tempfile.gettempdir(),self.DEFAULT_SOCKET_NAME)
	
	def forkServer(self,context,stdout=None,stderr=None):
		# Am I the new server process?
		if os.fork() == 0:
			with daemon.DaemonContext(detach_process=False,stdout=stdout,stderr=stderr) as context:
				slock = RWFileLock(self.serverLockFile)
				try:
					try:
						slock.w_lock()
					except LockError:
						# Other one controls all
						# Gracefully exit
						if stderr is not None:
							stderr.write(str(time.time())+"\nLOCKED\n")
						sys.exit(1)
					
					try:
						# At this point, we should be the only ones controlling this socket
						# As it is a UNIX one, its dir entry must be removed on each usage
						if os.path.exists(self.serverSocket):
							os.unlink(self.serverSocket)
						with socketserver.UnixStreamServer(self.serverSocket,self.handlerClass) as server:
							server.config = self.config
							server.context = context
							server.serve_forever()
					except:
						if stderr is not None:
							import traceback
							stderr.write(str(time.time())+"\n")
							traceback.print_exc(None,stderr)
				finally:
					if(slock.isLocked):
						slock.unlock()
					del slock
				
				sys.exit(0)
		
		return True
		
	def contactServer(self,context=None,stdout=None,stderr=None):
		retries = 2
		while retries > 0:
			retries -= 1
			# First, try connecting the server
			# through its socket
			sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			
			try:
				sock.connect(self.serverSocket)
				
				return sock
			
			except (FileNotFoundError,ConnectionRefusedError):
				# They are managed later
				sock.close()
			except socket.error as msg:
				if stderr is not None:
					import pprint
					pprint.pprint(msg,stream=stderr)
				raise msg
			
			# If there is no connection
			# then it's time to spawn the server process
			if retries > 0 and self.forkServer(context,stdout=stdout,stderr=stderr):
				# Sleep for 100ms
				time.sleep(0.1)
			else:
				break
		
		return None
	
	def talkServer(self,label,payload,context=None,stdout=None,stderr=None):
		sock = self.contactServer(context=context,stdout=stdout,stderr=stderr)
		
		rLabel = None
		rPayload = None
		
		if sock is not None:
			with sock:
				# First, send the message
				BGRequestHandler.SendMessage(sock,label,payload)
				
				# Now, waiting for the answer
				rLabel , rPayload = BGRequestHandler.RecvMessage(sock)
					
		return rLabel, rPayload