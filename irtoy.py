#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from lib import irtoy, ir
from serial import SerialTimeoutException

class ParseError(Exception):
	pass

def parseTime (timestr):
	""" helper: parse time duration string like "10_s" or "100_ms" """
	factors = {
		'ms': 0.001, 
		's':  1, 
		'm': 60,
		'h': 60 * 60
	}
	val, _, unit = timestr.partition('_')
	try:
		return int(val) * factors[unit]
	except (ValueError, KeyError) as e:
		print (' Invalid time: {:s}'.format(timestr))
		raise ParseError
	

def buttonMapToFile(filename, btns):
	try:
		with open(filename, "w") as f:
			for name, ir in btns.items():
				f.write("{:s}:{:s}\n".format(name, ir))
	except IOError:
		return False
	return True


def buttonMapFromFile(filename):
	""" read file and contruct dict with name->IRSignal mapping or None on failure """
	btns = {}
	try:
		for line in open(filename):
			if line.startswith('#'):
				continue
			name, data = line.split(':', 1)
			protocol, *params = data.split('|')
			try:
				btns[name] = getattr(ir, 'Ir'+protocol+'Signal')(*map(int,params))
			except AttributeError as e:
				return None
		return btns
	except IOError as e:
		return None

def confirm (promt, defaultYes=True):
	""" helper: ask y/n input with default, return True or False """
	return input(promt + (' [Y/n] ' if defaultYes else ' [y/N] ')) in (['y', 'Y', ''] if defaultYes else ['y', 'Y'])


def main():
	parser = argparse.ArgumentParser(description="Perform some actions with the usb IrToy such as record an IR stream")
	
	subparsers = parser.add_subparsers(help="action to perform", dest="action")
	
	parser_rec = subparsers.add_parser("record", help="record a raw IR stream to file")
	parser_play = subparsers.add_parser("play", help="play a raw IR stream from file")
	parser_btn = subparsers.add_parser("buttons", help="scan remote control buttons and write a buttonmap to file")
	parser_macr = subparsers.add_parser("macro", help="play a button macro using FILE as button map")
	
	parser_macr.add_argument("macro", metavar="MACRO", help="Macro to play, format is a sequence of "
						+"buttonName[:durationToHold] and/or .durationToWait commands, "
						+"separated by spaces. Durations have the format N_unit where N " 
						+"is the number of units (ms, s, m, h) to wait. "
						+"Example: \"on nextTrack volUp:500_ms .1_m off\": press button named 'on', then 'nextTrack', "
						+"hold 'volUp' for 500 milliseconds, wait a minute and press 'off'")
	
	parser.add_argument("file", help="File to use", metavar="FILE")
	parser.add_argument("--device", "-d", help="Serial port to use (default %(default)s)", default="/dev/ttyACM0")
	parser.add_argument("-q", "--quiet", action="store_false", dest="verbose", default=True)	
	
	args = parser.parse_args()
	
	try:
		if args.verbose:
			print ('Open and reset device... ')
		toy = irtoy.init(args.device)
		if not toy:
			print ('Failed!\n')
			return 1
		if args.verbose:
			print ('Done.\n')
		
		if args.action == "play":
			ver = irtoy.version(toy)
			if args.verbose:
				print('IR-Toy {}, firmware v{}'.format(*ver))
			if not ver[1] >= 20:
				print ('Error: !!OUTDATED FIRMWARE!! Please upgrade to v20 or newer.\n')
				return 1
			
			try:
				if args.verbose:
					print ('Reading input file...')
				data = open(args.file, "rb").read()
				if args.verbose:
					print ('Done\n')
			except IOError as e:
				print('Error: cannot read file {:s}\n'.format(args.file))
				return 1
		
			if args.verbose:
				print ('Start IR sampling mode...')
			ver = irtoy.enterSampleMode(toy)
			if args.verbose:
				print ('Done. Protocol Version {}\n'.format(ver))
			
			if args.verbose:
				print ('Transmitting...')
			success = irtoy.transmit(toy, data)
			if args.verbose or not success:
				print ('Success!\n' if success else 'Failed!\n')
			
			irtoy.exitSampleMode(toy)
			
			return int(not success)
		
		if args.action == "record":
			if args.verbose:
				print ('Start IR sampling mode...')
			ver = irtoy.enterSampleMode(toy)
			if args.verbose:
				print ('Done.\n')
			
			print ('Recording started, waiting for IR signals...')
			data = irtoy.record(toy)
			
			if args.verbose:
				print ('Recording done. Writing output file...')
			try:
				open(args.file, "wb").write(data)
				if args.verbose:
					print ('Done\n')
			except IOError as e:
				print('Error!\n')
				return 1
			finally:
				irtoy.exitSampleMode(toy)
			
			return 0
		
		if args.action == "buttons":			
			btns = buttonMapFromFile(args.file) or {}
			
			while True:
				print ('Please press a button on the remote')
				
				irtoy.enterSampleMode(toy)
				data = irtoy.record(toy)
				irtoy.exitSampleMode(toy)
				
				irCmd = ir.analyse(ir.calculatePulseTimes(data))
				
				if not irCmd:
					print ('Error: Unknown IR protocol.')
				else:
					if irCmd not in btns.values() or confirm('Warning: Button already saved. Save?', False):
						while True:
							btnName = input("Name of the button: ")
							if btnName.startswith(".") or ':' in btnName:
								print("Name should not start with a dot or contain colons!")
							else:
								break
						if btnName not in btns or confirm('Warning: Name already taken. Override?', False):
							btns[btnName] = irCmd
				if not confirm("Record more?"):
					break
			if not buttonMapToFile(args.file, btns):
				print('Error: cannot write output file.')
				return 1
			elif args.verbose:
				print('File {} written'.format(args.file))
		
		if args.action == "macro":
			import time
			try:
				if args.verbose:
					print('Parsing macro...')
				stream = bytearray()
				stops = [] # tuples of (stopindex, sleeptime_s)
				btns = buttonMapFromFile(args.file)
				if not btns:
					print('Cannot read button map file.\n')
					return 1
				for cmd in args.macro.split():
					if cmd.startswith('.'):
						stops.append((len(stream), parseTime(cmd[1:])))
					else:
						btn, _, dur = cmd.partition(':')
						try:
							stream.extend(ir.calculateRawData(btns[btn].pulses(parseTime(dur)*1000 if dur else 0)))
							if (len(stream)/2) % 2: # wait 150 ms after this key
								stream.extend(ir.calculateRawData([150*1000]))
						except KeyError as e:
							print ('Button {:s} not found in mapfile!'.format(btn))
							raise ParseError
				if args.verbose:
					print ('Done\n')
				
				if args.verbose:
					print('Transmitting...')
				ret = []
				laststop = 0
				for stop, delay in stops:
					irtoy.enterSampleMode(toy)
					ret.append(irtoy.transmit(toy, stream[laststop:stop]))
					irtoy.exitSampleMode(toy)
					laststop = stop
					time.sleep(delay)
				irtoy.enterSampleMode(toy)
				ret.append(irtoy.transmit(toy,stream[laststop:]))
				irtoy.exitSampleMode(toy)
				success = all(ret)
				if args.verbose or not success:
					print('Success!\n' if success else 'Failed!\n')
				
			except ParseError as e:
				print ('Error: cannot parse Macro\n')
				return 1

		
	except irtoy.RecievedGarbageException as e:
		print ('Error: device sent garbage. Please restart it by unplugging and plug in again.')
		return 1

	except SerialTimeoutException as e:
		print ('Error: connection timed out.')
		return 1
	
	finally:
		toy.close()

	
	return 0

if __name__ == '__main__':
	main()
