import select
import traceback
import socket
import sys
import Queue
import time
import datetime
import ssl

PORT=8005
HOST='127.0.0.1'

#35.153.115.14
#targetEndpoint = ('10.13.9.28',443);
targetEndpoint = ('35.153.115.14',443);
multEndpoints=[targetEndpoint] # osb.bovnt.com

def ts():
		st = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d %H:%M:%S')
		return st

def connectToSock(address):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		if (address[1] == 443):
				print("wrapping in ssl...")
				s=ssl.wrap_socket(s, ssl_version=ssl.PROTOCOL_SSLv23)
		s.setblocking(0)
		s.settimeout(5)
		print 'attempting to connect to '+str(address[0]),' ',str(address[1])
		s.connect((address[0], address[1]))
		return s

def closeCorrespondingSocket(sock,clientToServerMap,serverToClientMap,inputs,outputs):
		if (clientToServerMap.has_key(sock)):
				if clientToServerMap[sock][0] in outputs:
						outputs.remove(clientToServerMap[sock][0])
				if clientToServerMap[sock][0] in inputs:
						inputs.remove(clientToServerMap[sock][0])
				clientToServerMap[sock][0].close()
				clientToServerMap.pop(sock,None)
		else:
				if serverToClientMap[sock][0] in outputs:
						outputs.remove(serverToClientMap[sock][0])
				if serverToClientMap[sock][0] in inputs:
						inputs.remove(serverToClientMap[sock][0])
				serverToClientMap[sock][0].close()
				serverToClientMap.pop(sock,None)
	   

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
multEndpointsSock=map(connectToSock,multEndpoints)

clientToServerMap={}
serverToClientMap={}

try:
		print("listening on "+HOST+":"+str(PORT));

		server.setblocking(0)
		server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		server.bind((HOST,PORT))
		server.listen(5)


		inputs=[ server ]
		outputs= []
		responder=multEndpointsSock[0]
		connectors=[]
		dataOut=None
		response=None
		notifiers=0
		queue = []

		while inputs:
				try:
						print("selecting..")
						print("inputs: "+str(inputs))
						print("outputs: "+str(outputs))
						print("server: "+str(server))
						if server not in inputs:
								print("appending server...");
								inputs.append(server)
						readable, writable, exceptional = select.select(inputs, outputs, inputs)

						for s in readable:

								if s is server:
										print("connected with server")
										# A "readable" server socket is ready to accept a connection
										connection, client_address = s.accept()
										print ">>>>>> "+ts()+" new connection from", str(client_address)
										connection.setblocking(0)
										inputs.append(connection)

										if (connection.getpeername() not in multEndpoints):
												connectors.append(connection)
												serverSock=connectToSock(targetEndpoint)
												clientToServerMap[connection]=[serverSock,""]
												serverToClientMap[serverSock]=[connection,""]

										print("serverToClientMap: "+str(serverToClientMap))
										print("clientToServerMap: "+str(clientToServerMap))

										# Give the connection a queue for data we want to send
								else:
										print ">>>>>> "+ts()+" reading from  " +str(s.getpeername())
										data = s.recv(1024)
										print(data)
										print("==========================================")
										print("checking data...");
										if data:
												print("for data")
												if (clientToServerMap.has_key(s)):
														print("for data 1.1")
														outputs.append(clientToServerMap[s][0])
														serverToClientMap[clientToServerMap[s][0]][1]=serverToClientMap[clientToServerMap[s][0]][1]+data
														print("for data 1.15")
												else:
														print("for data 1.2")
														outputs.append(serverToClientMap[s][0])
														clientToServerMap[serverToClientMap[s][0]][1]=clientToServerMap[serverToClientMap[s][0]][1]+data
												print("for data 2")
										else:
											
											# Interpret empty result as closed connection
											# Stop listening for input on the connection
											'''print("no data...")
											if (clientToServerMap.has_key(s)):
													if clientToServerMap[s][0] in outputs:
															outputs.remove(clientToServerMap[s][0])
													if clientToServerMap[s][0] in inputs:
															inputs.remove(clientToServerMap[s][0])
													clientToServerMap[s][0].close()
													clientToServerMap.pop(s,None)
											else:
													if serverToClientMap[s][0] in outputs:
															outputs.remove(serverToClientMap[s][0])
													if serverToClientMap[s][0] in inputs:
															inputs.remove(serverToClientMap[s][0])
													serverToClientMap[s][0].close()
													serverToClientMap.pop(s,None)'''

										print("serverToClientMap: "+str(serverToClientMap))
										print("clientToServerMap: "+str(clientToServerMap))
										if s in outputs:
											outputs.remove(s)
										inputs.remove(s)
										

						# Handle outputs
						for s in writable:
								print("for writing: peername: "+str(s.getpeername()))
								print("response to write: "+str(response))
								if (clientToServerMap.has_key(s)):
										print("client")
										inputs.append(clientToServerMap[s][0])
										data=clientToServerMap[s][1]
										clientToServerMap[s][1] = ""
								else:
										print("server")
										inputs.append(serverToClientMap[s][0])
										data=serverToClientMap[s][1]
										serverToClientMap[s][1] = ""

								print("writing data "+data)
								s.send(data)

								if s not in inputs:
										inputs.append(s)
								outputs.remove(s)

						# Handle "exceptional conditions"
						for s in exceptional:
								print >>sys.stderr, 'handling exceptional condition for', s.getpeername()
								# Stop listening for input on the connection
								inputs.remove(s)
								if s in outputs:
										outputs.remove(s)
								s.close()
				except:
						print("error")
						traceback.print_exc(file=sys.stdout)
						toremove=[]
						for i in inputs:
								try:
										print(i.fileno())
								except:
										toremove.append(i)
						for i in toremove:
								print("removing "+str(i))
								inputs.remove(i)
								i.close()
								closeCorrespondingSocket(i,clientToServerMap,serverToClientMap,inputs,outputs)

						toremove=[]
						for i in outputs:
								try:
										print(i.fileno())
								except:
										toremove.append(i)
						for i in toremove:
								print("removing "+str(i.getpeername()))
								outputs.remove(i)
								i.close()
								closeCorrespondingSocket(i,clientToServerMap,serverToClientMap,inputs,outputs)


except Exception:
		traceback.print_exc(file=sys.stdout)

print "closing connection"
server.close()
for i in multEndpointsSock:
		print "closing %s %s" % (i.getpeername())
		i.close()
