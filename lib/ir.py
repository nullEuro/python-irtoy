#!/usr/bin/env python3
# -*- coding: utf-8 -*-

""" This module contains classes and functions to analyse raw data from the IR hardware """

class IRSignal:
	""" base class for IR protocol signals """
	@staticmethod
	def matches(pulses):
		""" check if list of pulses matches this protocol """
		raise NotImplementedError
	@staticmethod
	def construct(pulses):
		""" get signal instance for this list of pulses """
		raise NotImplementedError
	def pulses(self, duration=0):
		""" get list of IR pulse/spare times, in microseconds for this signal (button press) with duration """
		raise NotImplementedError
	def __init__ (self):
		pass

class IrNECSignal (IRSignal):
	""" class for the IR NEC protocol """
	@staticmethod
	def matches(pulses):
		return len(pulses) >= 4 * 8 * 2 + 3 and aeq(pulses[0], 9000) and aeq(pulses[1], 4500)
	@staticmethod
	def construct(pulses):
		data = [0, 0, 0, 0]
		for i in range(4):
			# i-th byte pulses!
			start, stop = 3 + i * 8 * 2,	3 + (i+1) * 8 * 2
			for bit, space in enumerate(pulses[start:stop:2]):
				if aeq(space, 1690):
					data[i] |= 0b10000000 >> bit
		if data[2] ^ data[3] != 0b11111111:
			print ("Malformed data")
			return None
		print ("AddrLo: 0x{:02X}  AddrHi: 0x{:02X} Cmd: 0x{:02X}".format(*data))
		return IrNECSignal(data[0], data[1], data[2])
	
	def __init__(self, addrLo, addrHi, cmd):
		if addrLo.bit_length() > 8 or addrHi.bit_length() > 8 or cmd.bit_length() > 8:
			raise ValueError
		self.addrHi = addrHi
		self.addrLo = addrLo
		self.cmd = cmd
	
	def __eq__(self, other):
		return self.addrHi == other.addrHi and self.addrLo == other.addrLo and self.cmd == other.cmd
	
	def __str__(self):
		return "NEC|{:d}|{:d}|{:d}".format(self.addrHi, self.addrLo, self.cmd)
		
	def pulses(self, duration=0):
		p = [9000, 4500]
		for b in [self.addrLo, self.addrHi, self.cmd, ~self.cmd]:
			for i in range(8):
				p.extend([560, 1690 if b & (0b10000000 >> i) else 560])
		p.append(560)
		if duration > 110:
			p.extend([110000-sum(p[0:3 + 4 * 8 * 2 + 1]), 9000, 2250, 560])
			p.extend([110000, 9000, 2250, 560] * (int(duration/110) - 1))
		return p
		
class IrRC5Signal (IRSignal):
	""" class for the IR RC5(X) protocol """
	@staticmethod
	def matches(pulses):
		return agt(sum(pulses), 1778*14) and agt(pulses[0], 889)
		
	@staticmethod
	def construct(pulses):
		bits = []
		last = False
		isBurst = True
		for time in pulses:
			if last is not None:
				bits.append(not last)
				if len(bits) == 14:
					break
				if aeq(time, 889):
					last = None
				elif aeq(time, 2 * 889):
					last = isBurst
				else:
					return None
			else:
				if aeq(time, 889):
					last = isBurst
				else:
					return None
			isBurst = not isBurst
		if last is not None:
			bits.append(not last)
		if len(bits) < 14:
			return None
		addr_bits, cmd_bits = bits[3:8], [not bits[1]] + bits[8:14]
		addr = sum(1<<i for i, b in enumerate(reversed(addr_bits)) if b)
		cmd = sum(1<<i for i, b in enumerate(reversed(cmd_bits)) if b)
		print ("Addr: 0x{:02X} Cmd: 0x{:02X}".format(addr, cmd))
		return IrRC5Signal(addr, cmd)
		
	
	def __init__(self, addr, cmd):
		if addr.bit_length() > 5 or cmd.bit_length() > 7:
			raise ValueError
		self.addr = addr
		self.cmd = cmd
		self.togglebit = False
	
	def __eq__(self, other):
		return self.addr == other.addr and self.cmd == other.cmd
	
	def __str__(self):
		return "RC5|{:d}|{:d}".format(self.addr, self.cmd)
		
	def pulses(self, duration=0):
		data = self.addr << 6 | (self.cmd & 0b111111)
		bits = [True, not (self.cmd & 0b1000000), self.togglebit] + [bool(data & (0b1 << i)) for i in reversed(range(5+6))]
		pulses = []
		lastbit = bits[0]
		for bit in bits[1:]:
			if bit == lastbit:
				pulses.extend([889,889])
			else:
				pulses.append(1778)
			lastbit = bit
		if lastbit:
			pulses.append(889)
		if duration > 114:
			pulses.append(114*1000 - 1778*14) # wait 114ms between repeats
		self.togglebit = not self.togglebit
		return pulses * int(duration/114 + 1)
		

def analyse (pulses):
	"""  Analyse list of pulse/spare times (in microseconds) and return instance of signal type class or None """
	for cls in IRSignal.__subclasses__():
		if cls.matches(pulses):
			return cls.construct(pulses)
	return None

def calculatePulseTimes(data):
	""" get pulse/spare time list (in microseconds) from raw IR data """
	return [((p[0] << 8) | p[1]) * 21.3333 for p in chunker(data, 2)]

def calculateRawData(pulses):
	""" get raw IR data from list of pulse/spare times """
	b = bytearray()
	for p in pulses:
		b.extend([int(p/21.3333) >> 8, int(p/21.3333) & 0xFF])
	return b

def chunker(seq, size):
	""" helper: chunk a list """
	return (seq[pos:pos + size] for pos in range(0, len(seq), size))

# aproximately equal
def aeq(v1, v2, tolerance = 0.15):
	""" helper: check if v1 and v2 are aproximately equal """
	return abs(v1 - v2) <= v2 * tolerance

# aproximately equal or greater than
def agt(v1, v2, tolerance = 0.15):
	""" helper: check if v1 is greater than or aproximately equal to v2 """
	return v1 >= v2 * (1 - tolerance)
