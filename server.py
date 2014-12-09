#!/usr/bin/python
# encoding: utf-8

from asyncore import dispatcher
from asynchat import async_chat
import socket, asyncore

PORT = 6666 #端口

class EndSession(Exception):
    """
    自定义会话结束时的异常
    """
    pass

class CommandHandler:
    """
    命令处理类
    """

    def unknown(self, session, cmd):
        '响应未知命令'
        session.push('Unknown command: %s\n' % cmd)

    def handle(self, session, line):
        '命令处理'
        if not line.strip():
            return
        parts = line.split(' ', 1)
        cmd = parts[0]
        try:
			line = parts[1].strip()
        except IndexError:
			line = ''
        meth = getattr(self, 'do_' + cmd, None)
        try:
			meth(session, line)
        except TypeError:
			self.unknown(session, cmd)

class Room(CommandHandler):
    """
    包含多个用户的环境，负责基本的命令处理和广播
    """

    def __init__(self, server):
		self.server = server
		self.sessions = []

    def add(self, session):
        '一个用户进入房间'
        self.sessions.append(session)

    def remove(self, session):
        '一个用户离开房间'
        self.sessions.remove(session)

    def broadcast(self, line):
        '向所有的用户发送指定消息'
        for session in self.sessions:
            session.push(line)

    def do_logout(self, session, line):
        '退出房间'
        raise EndSession

class LoginRoom(Room):
    """
    刚登录的用户的房间
    """

    def add(self, session):
        '用户连接成功的回应'
        Room.add(self, session)
        session.push('Connect Success')

    def do_login(self, session, line):
        '登录命令处理'
        name = line.strip()
        if not name:
            session.push('UserName Empty')
        elif name in self.server.users:
            session.push('UserName Exist')
        else:
            session.name = name
            session.enter(self.server.main_room)

class ChatRoom(Room):
    """
    聊天用的房间
    """

    def add(self, session):
        '广播新用户进入'
        session.push('Login Success')
        self.broadcast(session.name + ' has entered the room.\n')
        self.server.users[session.name] = session
        Room.add(self, session)

    def remove(self, session):
        '广播用户离开'
        Room.remove(self, session)
        self.broadcast(session.name + ' has left the room.\n')

    def do_say(self, session, line):
        '客户端发送消息'
        self.broadcast(session.name + ': ' + line + '\n')

    def do_look(self, session, line):
        '查看在线用户'
        session.push('Online Users:\n')
        for other in self.sessions:
            session.push(other.name + '\n')

class LogoutRoom(Room):
    """
    用户退出时的房间
    """

    def add(self, session):
        '从服务器中移除'
        try:
            del self.server.users[session.name]
        except KeyError:
            pass

class ChatSession(async_chat):
    """
    负责和单用户通信
    """

    def __init__(self, server, sock):
		async_chat.__init__(self, sock)
		self.server = server
		self.set_terminator('\n')
		self.data = []
		self.name = None
		self.enter(LoginRoom(server))

    def enter(self, room):
        '从当前房间移除自身，然后添加到指定房间'
        try:
            cur = self.room
        except AttributeError:
            pass
        else:
            cur.remove(self)
        self.room = room
        room.add(self)

    def collect_incoming_data(self, data):
        '接受客户端的数据'
        self.data.append(data)

    def found_terminator(self):
        '当客户端的一条数据结束时的处理'
        line = ''.join(self.data)
        self.data = []
        try:
            self.room.handle(self, line)
        except EndSession:
            self.handle_close()

    def handle_close(self):
		async_chat.handle_close(self)
		self.enter(LogoutRoom(self.server))

class ChatServer(dispatcher):
    """
    聊天服务器
    """

    def __init__(self, port):
		dispatcher.__init__(self)
		self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
		self.set_reuse_addr()
		self.bind(('', port))
		self.listen(5)
		self.users = {}
		self.main_room = ChatRoom(self)

    def handle_accept(self):
		conn, addr = self.accept()
		ChatSession(self, conn)

if __name__ == '__main__':
	s = ChatServer(PORT)
	try:
		asyncore.loop()
	except KeyboardInterrupt:
		print
