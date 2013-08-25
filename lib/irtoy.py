#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from  serial import *
import time

class AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self

commands = AttrDict(dict(
	DataEnd=			 bytes.fromhex(u'ff ff'),
	reset=			 bytes.fromhex(u'00 00 00 00 00'),
	getFWVersion=	b'v',
	
	sample= AttrDict(dict( # sample mode commands
		init=				b'S',
		reset=			b'\x00',
		transmit=		b'\x03', # ends with commands.DataEnd
		ledMute=			b'\x10',
		ledUnmute=		b'\x11',
		ledOn=			b'\x12',
		ledOff=			b'\x13',
		reportSentCnt=	b'\x24',
		reportComplete=b'\x25', 
		useHandshake=	b'\x26', 
	)),
))

class RecievedGarbageException(Exception):
	def __init__(self, message = None):
		super().__init__(message)


def init(port="/dev/ttyACM0"):
	""" prepare device: open serialport port, send transmit end, reset code and flush data """
	try:
		toy = Serial(port=port, baudrate=115200, timeout=2)
		toy.write(commands.DataEnd); time.sleep(25/1000)
		toy.flush()
		toy.write(commands.reset)
	except SerialException as e:
		print ('Error: cannot open serial port %s: %s' % (port, e.strerror))
		return None
	return toy

def version(toy):
	""" return a tuple of (hardware, firmware) version """
	toy.write(commands.getFWVersion)
	data = toy.read(4)
	try:
		hw, fw = data[:2], int(data[2:])
	except ValueError as e:
		raise RecievedGarbageException
	return hw.decode("utf-8"), fw
	
def enterSampleMode(toy):
	""" enter IR sample mode and return protocol version """
	toy.write(commands.sample.init)
	data = toy.read(3)
	try:
		s, ver = chr(data[0]), int(data[1:])
	except ValueError as e:
		raise RecievedGarbageException	
	if s != 'S':
		raise RecievedGarbageException
	return ver
	
def exitSampleMode(toy):
	""" enter IR sample mode and return protocol version """
	toy.write(commands.sample.reset)

def record(toy):
	""" record and return raw data from toy, asuming it is in sampling mode """
	data = bytearray()
	signalEnd = False
	while not signalEnd:
		chunk = toy.read(2)
		data.extend(chunk)
		signalEnd = data.endswith(commands.DataEnd)
	return data[:-len(commands.DataEnd)]

def transmit(toy, data):
	""" send IR data to the IrToy and transmit. Device needs to be in sample mode. Return True on success """
	if not data:
		return True
	toy.write(commands.sample.reportSentCnt)
	toy.write(commands.sample.reportComplete)
	toy.write(commands.sample.useHandshake)
	toy.write(commands.sample.transmit)
	
	sent, toyBufferSize = 0, toy.read(1)[0]
	while sent < len(data):
		toy.write(data[sent:sent + toyBufferSize])
		sent += toyBufferSize
		toyBufferSize = toy.read(1)[0]
	
	toy.write(commands.DataEnd); toy.read(1) # ignore last handshake
	total = toy.read(3)
	if chr(total[0]) != 't':
		raise RecievedGarbageException
	status = chr(toy.read(1)[0])
	return (total[1] << 8) | total[2] == len(data) + 2 and status == 'C'
