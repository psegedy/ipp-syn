#!/usr/bin/env python3

#SYN:xseged00
import re
import sys
import argparse
import os

# Parse arguments and check argument validity
def checkArgs(argv):
	parser = argparse.ArgumentParser(add_help=False)
	parser.add_argument('--input', nargs='?', default=sys.stdin)
	parser.add_argument('--output', nargs='?', default=sys.stdout)
	parser.add_argument('--format', nargs='?')
	parser.add_argument('--br', action='store_true', default=False)
	parser.add_argument('--help', action='store_true', default=False)
	
	# try to parse arguments, if exception is trew, exit with err code 1
	try:
		args = parser.parse_args()
	except:
		print('Wrong arguments', file=sys.stderr)
		exit(1)

	# if input is not set, use stdin
	if args.input == None or args.input == "":
		args.input = sys.stdin
	# if input is not set, use stdout
	if args.output == None or args.output == "":
		args.output = sys.stdout
	# print help message
	if args.help:
		if len(argv) == 2:
			print("""
--help 	viz společné zadání všech úloh
--format=filename 	určení formátovacího souboru. Soubor bude obsahovat libovolné
			množství formátovacích záznamů. Formátovací záznam se bude skládat z regulárního výrazu
			vymezujícího formátovaný text a příkazů pro formátování tohoto textu. Detailní popis viz níže.
--input=filename 	určení vstupního souboru v kódování UTF-8.
--output=filename 	určení výstupního souboru opět v kódování UTF-8 s naformátovaným
			vstupním textem. Formátování bude na výstupu realizováno některými HTML elementy na
			popis formátování. Regulární výrazy ve formátovacím souboru určí, který text se naformá-
			tuje, a formátovací informace přiřazené k danému výrazu určí, jakým způsobem se tento text
			naformátuje.
--br 	přidá element <br /> na konec každého řádku původního vstupního textu
					 """)
			exit(0)
		else:
			print('Wrong number of arguments', file=sys.stderr)
			exit(1)

	return args

# get list of lists from format file
# [['regex','formatting commands'],[]]
def readFormatFile(formatfd):
	formatList = []
	for line in formatfd:
		# skip empty lines
		if line == '\n':
			continue
		try:
			parts = ()
			formatListPart = []
			# split line by \t
			# parts[0] - string before \t
			# parts[1] - sequence of \t
			# parts[2] - string after \t
			parts = line.partition('\t')
			# if sequence of \t is empty
			if parts[1] == "":
				exit(4)
			# add parts[0] and parts[2] to list
			# ['parts[0]', 'parts[2]']
			formatListPart.append(parts[0])
			formatListPart.append(parts[2].strip('\n')) # get rid of \n at the end
			# append parts to list - [['parts[0]', 'parts[2]'],[...], ...]
			formatList.append(formatListPart)
		except:
			print('Bad format file', file=sys.stderr)
			exit(4)
			
	return formatList

# Converts given formatting commands to HTML tags
# returns list of tags e.g. ['<b>','<u>','<i>']
def convertTag(inTag, openTag):
	htmlTag = ''
	tagList = []
	formatCommands = ['bold', 'italic', 'underline', 'teletype']
	htmlTags = ['b', 'i', 'u', 'tt']
	tags = inTag.split(',')
	# iterate over tags in inTag
	for tag in tags:
		htmlTag += '<'
		if openTag == False:
			htmlTag += '/'
		tag = tag.strip()
		# font size
		matchedSize = re.match("size:([1-7])", tag)
		# font color
		matchedColor = re.match("color:([0-9a-fA-F]{6})", tag)
		if tag in formatCommands:
			i = 0
			# iterate over commands and assign correct tag
			for command in formatCommands:
				if tag == command:
					htmlTag += htmlTags[i]
				i += 1
		elif matchedSize != None:
			if openTag:
				htmlTag += 'font size=' + matchedSize.group(1)
			else:
				htmlTag += 'font'
		elif matchedColor != None:
			if openTag:
				htmlTag += 'font color=#' + matchedColor.group(1)
			else:
				htmlTag += 'font'
		else:
			print('Bad formatting command', file=sys.stderr)
			exit(4)
		htmlTag += '>'
		tagList.append(htmlTag)
		htmlTag = ''

	# if its end/close tag, then reverse list
	if openTag == False:
		tagList.reverse()	
	return tagList

# Converts given regular expression to python re
# returns string conatining converted regular expression
def convertRe(inRegex):
	# if inRegex starts/ends with dot, or has multiple dots
	if re.search('(?:^\.)|(?:[^%]\.\.+)|(?:[^%]\.$)', inRegex) != None:
		print('Bad format file - wrong regex', file=sys.stderr)
		exit(4)
	# starts/ends with | or multiple |
	if re.search('(?:^[|])|(?:[^%][|]$)|(?:^\|$)', inRegex) != None:
		print('Bad format file - wrong regex', file=sys.stderr)
		exit(4)
	# another | check 
	if re.search('(?:^\|\|)|(?:[^%]\|\|)', inRegex) != None:
		print('Bad format file - wrong regex', file=sys.stderr)
		exit(4)
	# empty brackets
	if re.search('[(][)]', inRegex) != None:
		print('Bad format file - wrong regex', file=sys.stderr)
		exit(4)
	# contains only ! or ends with !
	if re.search('(?:^!$)|(?:[^%]!$)', inRegex) != None:
		print('Bad format file - wrong regex', file=sys.stderr)
		exit(4)
	# .| or |.
	if re.search('(?:^\.\|)|(?:[^%]\.\|)|(?:^\|\.)|(?:[^%]\|\.)', inRegex) != None:
		print('Bad format file - wrong regex', file=sys.stderr)
		exit(4)

	# EXTENSION: NQS
	while re.search('(\*|\+){2,}', inRegex) != None:
		inRegex = re.sub('(\+\++)+', '+', inRegex); 	# A++ -> A+
		inRegex = re.sub('(\*\*+)+', '*', inRegex);		# A** -> A*
		inRegex = re.sub('(\++\*+)+', '*', inRegex);	# A+* -> A*
		inRegex = re.sub('(\*+\++)+', '*', inRegex);	# A*+ -> A*
	
	state = 'S'		# possible states: S, negate, perc
	neg = ''		# for negation, negation is neg = '^'
	reString = ''	# converted regex

	# iterate over regular expression char by char
	for i in range(0,len(inRegex)):
		#print('act part: '+inRegex[i])
		# state S
		if state == 'S':
			# go to state %
			if inRegex[i] == '%':
				state = 'perc'
			elif inRegex[i] == '!':
				# if .|)+* after ! and ! is not escaped by %
				if inRegex[i+1] in '.|)+*':
					if inRegex[i-1] != '%':
						print('Bad format file - wrong regex', file=sys.stderr)
						exit(4)
				# if negation is set -> neg = '' else neg = '^'
				neg = '' if neg == '^' else '^'
				# if negation is set and next char is ( go to state negate
				if inRegex[i+1] == '(':
					if neg == '^':
						state = 'negate'
			# escape \"'[]{}$?\^
			elif inRegex[i] in '\\\"\'[]{}$?\^' :
				if neg == '':
					reString += '\\' + inRegex[i]
				else:
					reString += '[^' + inRegex[i] + ']'
					neg = ''
			# error if there is . or | after (
			elif inRegex[i] == '(' :
				try:
					if inRegex[i+1] in '.|':
						print('Bad regex, | or . after (', file=sys.stderr)
						exit(4)
				except:
					exit(4)
				reString += inRegex[i]
			# skip dot
			elif inRegex[i] =='.':
				continue
			# other characters
			else :
				if neg == '^':
					reString += '[^' + inRegex[i] + ']'
				else:
					reString += inRegex[i]
		# state negate
		elif state == 'negate':
			# change ( to (?! - negative lookahead
			reString += '(?!'
			neg = ''
			state = 'S'
			# negate only 1 char
			if (i+2) < len(inRegex):
				if inRegex[i+1] not in '.|!+*%':
					if inRegex[i+2] not in '.|!+*%':
						print('Bad regex, multiple characters after nagation', file=sys.stderr)
						exit(4)
		# percent state
		elif state == 'perc':
			if inRegex[i] == 'a':
				if neg == '':
					reString += '.'
				else:
					reString += '(?!.)'
				reString += '.'
			elif inRegex[i] in '.|!*+()%':
				if neg == '':
					reString += '\\' + inRegex[i]
				else:
					reString += '[^' + inRegex[i] + ']'	
			elif inRegex[i] in 'sdlLwWtn':
				reString += '[' + neg
				parts = [' \t\n\r\f\v]','0-9]','a-z]','A-Z]','a-zA-Z]','a-zA-Z0-9]','\t]','\n]']
				p = 0
				for char in 'sdlLwWtn':
					if inRegex[i] == char:
						reString += parts[p]
					p += 1		
			else:
				print('Bad format file, non valid regex with %', file=sys.stderr)
				exit(4)
			neg = ''
			state = 'S'
	# try to compile, if it fails -> error 4
	try:
		re.compile(reString)
	except:
		print('Bad format file, non valid regex', file=sys.stderr)
		exit(4)

	return reString

# main function
def main(argv):
	# file descriptors
	infd = sys.stdin
	outfd = sys.stdout
	formatfd = sys.stdin
	# list containing regex and formatting commands
	formatList = []
	# check command line arguments
	args = checkArgs(argv)

	# open files
	if args.input != sys.stdin:
		try:
			infd = open(args.input, 'r')
		except:
			print('Failed to open input file', file=sys.stderr)
			exit(2)
	# read the input file
	infile = infd.read()
	# open output file
	if args.output != sys.stdout:
		try:
			outfd = open(args.output, 'w')
		except:
			print('Failed to open output file', file=sys.stderr)
			exit(3)
	# if format file is not set - write input to output
	if args.format == None or args.format == "":
		if args.br:
			outfile = outfile.replace('\n', '<br />\n')
		outfd.write(infile)
		outfd.close()
		infd.close()
		exit(0)
	# open format file
	if args.format != sys.stdin:
		try:
			formatfd = open(args.format, 'r')
		except:
			if args.br:
				outfile = outfile.replace('\n', '<br />\n')
			outfd.write(infile)
			outfd.close()
			infd.close()
			exit(0)

	# get list of lists from format file
	formatList = readFormatFile(formatfd)
	# try to convert tags, print error if there is bad tag
	for pair in formatList:
		convertTag(pair[1], True)
	# get list of tuples from tags and positions where to apply in input
	tagPos = [] # example tagPos = [(35, ['</u>', '</font>']), (0, ['<b>']), (...), ...]
	for pair in formatList:
		# if regex or format command is missing
		if pair[0] == '' or pair[1] == '\n':
			print('Bad format file', file=sys.stderr)
			exit(4)
		regex = convertRe(pair[0])
		# find where starts/ends searched expression
		foundIter = re.finditer(regex, infile, re.DOTALL)
		for found in foundIter:
			# append tuple containing position and tag to list
			if found.start() != found.end():
				tagPos.append((found.start(), convertTag(pair[1], True)))
				# for end tags, prepend to list (reverse, append, reverse)
				tagPos.reverse()
				tagPos.append((found.end(), convertTag(pair[1], False)))
				tagPos.reverse()
	
	# place tags at proper positions
	outfile = ''
	# iterate through all characters in input file
	for i in range(len(infile)):
		# iterate through every tuple in tagPos list
		for j in range(0, len(tagPos)):
			# if index i in input file match index in tuple
			if i == tagPos[j][0]:
				# iterate through list list of tags in tuple
				for tag in tagPos[j][1]:
					# write tag to outfile
					outfile += tag
		outfile += infile[i]
	# same as above, but writes tags after end of input
	for i in range(0, len(tagPos)):
		if tagPos[i][0] >= len(infile):
			for tag in tagPos[i][1]:
				outfile += tag

	# add br tag at end of lines
	if args.br:
		outfile = outfile.replace('\n', '<br />\n')
	# write to outfile
	try:
		outfd.write(outfile)
	except:
		exit(3)
	
	infd.close()
	outfd.close()
	formatfd.close()

if __name__ == "__main__":
	main(sys.argv)
