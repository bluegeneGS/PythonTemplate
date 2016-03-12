#-------------------------------------------------------------------------------
#Name: CommManager.py
#Author: XING YUTENG
#Created: 2015/01/12
#-------------------------------------------------------------------------------
'''
This is Asynchronous socket handler handler template for general client/server 
communications

If you want to start UDP sockets use SOCK_DGRAM, TCP then use TCP ESOCK_STREAM

Stream Socket(SOCK_STREAM):

    Dedicated & point-to-point channel between server and client.
    Use TCP protocol for data transmission.
    Reliable and Lossless.
    Data sent/received in the similar order.
    Long time for recovering lost/mistaken data

Datagram Socket(SOCK_DGRAM):

    No dedicated & point-to-point channel between server and client.
    Use UDP for data transmission.
    Not 100% reliable and may lose data.
    Data sent/received order might not be the same
    Don't care or rapid recovering lost/mistaken data

you can create the server/client the use asyncoreZ.loop() to enter a pooling loops
'''

import threading
import socket
import asynchatZ
import asyncoreZ

MAXCONNECTION = 10  #only allow 10 connections at the same time
CONNECT_TIMEOUT = 20
MAX_LEN_PACKET = 4096
class CommChan(asynchatZ.async_chat):
    """This class handles communication with the remote, it is initiated when remote
    get a connect request on our ports
    """
    def __init__(self, sock, remote_address, parent, unit_id, terminator = None, timeout = CONNECT_TIMEOUT):
        """Start a communication Channel after connection request
        sock: socket to talk on and None if we are a client
        remote_address: ip address of the remote connection side
        parent: handle to parent CommServer/CommClient we are working with
        unit_id: id of this channel in string format
        terminator: terminating string or None
        """
        self.parent = parent
        self.remote_address = remote_address
        self.unit_id = unit_id
        asynchatZ.async_chat.__init__(self, sock)
        self.set_terminator(terminator)
        self.sendingLock = threading.Lock()
        
        try:
            if sock is None:
                # we are client - try to connect to the remote TCP server
                self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
                self.connect(remote_address)
            else:
                # if server, we are handling a connection request
                self.handle_connect()
        except IOError:
            self.close()
            raise
    
    def __str__(self):
        return "CommChan: %s, remote_adress: %s", (self.unit_id, self.remote_address)
    
    def close(self):
        """handle the close socket call
        detach the parent and inform the parent to disconnected related works
        """
        parent = self.parent
        if parent:
            self.parent = None
            try:
                if self.connected:
                    parent.openCloseCallback(self, 'disconnect')
                asynchatZ.async_chat.close(self)
            except:
                pass
    
    def collect_incoming_data(self, data):
        self._collect_incoming_data(data)
    
    def found_terminator(self):
        data = self._get_data()
        self.processData(data)

    def processData(self, data):
        """Called to process the received data when terminator is found
        """
        #print "ConnChan %s get data: %s" %(self.unit_id, data)
        pass
        
    def handle_connect(self):
        """handle the connection request and inform the parents it is connected
        """
        self.connected = True
        self.parent.openCloseCallback(self, 'connect')
    
    def handle_close(self):
        """This is override of asynchat.handle_close. We are called when the channel
        gets closed, whether due to error, deliberate close from here, or close from
        remote side.
        """
        #log the errors
        #err = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
        self.close()
        
    def sendStr(self, data, need_terminator = True):
        """Send data as a string attached with the terminator we defined
        """
        with self.sendingLock:
            if need_terminator and data[-1] != self.terminator:
                data = data + self.terminator
            self.send(data)


class CommClient(object):
    """Communication server for generic clients"""
    def __init__(self, address, terminator, instance_name, cbRtn, timeout = CONNECT_TIMEOUT):
        """address is the server ip and port we are listening on as (ip, port)
        terminator is asynchat terminator
        cnRtn is the call back routine typically as cbConnected that we call when we
        are connected or disconnected
        """
        self.ip_adress = address
        self.terminator = terminator
        self.cbRtn = cbRtn
        self.clientCommChannel = None
        self.clientCommChannel = CommChan(None, address, self, instance_name, terminator, timeout)
    
    def openCloseCallback(self, command):
        """Callback from CommChan when channel opened or closed
        chanHandle: CommChan instance
        command: 'connect' or 'disconnect'
        """
        cbRtn = self.cbRtn
        try:
            if cbRtn:
                cbRtn(self, command)
        except:
            pass
    
    def stop(self):
        """if program shutting done, close all connection"""
        try:
            if self.clientCommChannel:
                self.clientCommChannel.close()
            self.clientCommChannel = None
        except:
            #Comm what might went wrong 
            pass


class CommServer(object):
    """Set up a communication server"""
    def __init__(self, address, terminator, cbRtn):
        """address is the server ip and port we are listening on as (ip, port)
        terminator is asynchat terminator
        cnRtn is the call back routine typically as cbConnected that we call when we
        are connected or disconnected
        connectedChannels keeps records of all connected channels(CommChan) in a list
        """
        self.connectedChannels = []
        self.ip_address = address
        self.string_terminator = terminator
        self.cnRtn = cbRtn
        self.connectionServer = None
        self.connectionServer = ConnectionServer(address, self, terminator)
    
    def openCloseCallback(self, chanHandle, command):
        """Callback from CommChan when channel opened or closed
        chanHandle: CommChan instance
        command: 'connect' or 'disconnect'
        """
        cbRtn = self.cnRtn
        try:
            if cbRtn:
                cbRtn(chanHandle, command)
            if command == 'disconnect':
                self.connectedChannels.remove(chanHandle)
        except:
            pass
    
    def stop(self):
        """if program shutting done, close all connection"""
        try:
            for chan in self.connectedChannels:
                chan.close()
            self.connectedChannels = []
        except:
            #Comm what might went wrong
            pass

           
class ConnectionServer(asyncoreZ.dispatcher):
    """This is worker for CommServer. we watch for connection on our listening
    ports, then create a communication channel as instance of CommChan to handle
    all communication with the remote device.
    """
    def __init__(self, address, parent, terminator = None):
        """address is ip address and port server listening on,
        parent is CommServer, terminator is the string terminitor or None
        """
        self.parent = parent
        self.terminator = terminator
        asyncoreZ.dispatcher.__init__(self)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)  #TCP
        self.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  #make it reusable
        self.bind(address)
        self.listen(MAXCONNECTION)  #can get this maximum connections
        self.id_count = 0
    
    def handle_accept(self):
        """handle the connection request and create the communication channel
        count will be treated as the unit id for each different channel created
        """
        try:
            conn, address = self.accept()
            self.id_count += 1
            self.parent.connectedChannels.append(CommChan(conn, 
                                                         address, 
                                                         self.parent, 
                                                         str(self.id_count),
                                                         self.terminator))
        except TypeError:
            err = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            raise


class UDPRemoteRecv(asynchatZ.async_chat):
    def __init__(self, addr, cbRtn = None):
        """Set up receive only channel to get UDPs from remote
        addr: (ip, port)
        cbRtn: call back routine to handle data or None for no cbRtn
        """
        asynchatZ.async_chat.__init__(self)
        self.addr = addr
        self.cbRtn = cbRtn
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)   #UDP
        self.bind(addr)

#-----------------------------------------------------------------------------
    def collect_incoming_data(self, data):
        #should not happen because it is for read only
        self.data = self.data + data

#-----------------------------------------------------------------------------
    def handle_read(self):
        data = self.socket.recv(MAX_LEN_PACKET)
        cbRtn = self.cbRtn
        if cbRtn:
            try:
                cbRtn(data)
            except:
                #'COMM RemoteRecv handle_read had err on str %s', data
                pass
        else:
            #no cbRtn then handle data here
            pass

#-----------------------------------------------------------------------------
    def readable(self):
        return True

#-----------------------------------------------------------------------------
    def writable(self):
        return False

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
class UDPRemoteSend(asynchatZ.async_chat):
    def __init__(self, addr):
        """Set up send only channel to send UDP to remote.
        addr: (ip, port)
        """
        asynchatZ.async_chat.__init__(self)
        self.addr = addr
        self.data = ''
        self.create_socket(socket.AF_INET, socket.SOCK_DGRAM)   #UDP

#-----------------------------------------------------------------------------
    def handle_write(self):
        try:
            if self.data:
                self.socket.sendto(self.data, self.addr)
                self.data = ''
        except:
            pass

#-----------------------------------------------------------------------------
    def readable(self):
        #send only udp socket
        return False

#-----------------------------------------------------------------------------
    def sendData(self, data):
        """Queues a data block to be sent"""
        self.data = data

#-----------------------------------------------------------------------------
    def writable(self):
        return len(self.data) > 0
    