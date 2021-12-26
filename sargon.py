import z80 # https://github.com/arpruss/z80
import binascii
import time
import sys
import cv2
import numpy as np
import hp1345
import readhex
import readlst
import math
        
def gamepadEvents(): return []
def haveGamepad(): return False

MINIMUM_COMPUTE_TIME_PER_FRAME = 1. / 5
ZOOM = 10
FLOODFILL = True
CHECK_FOR_COMPUTER_REPEATS = True
WINDOW = "Sargon"

STATE_ASK_PLAY = 0
STATE_ASK_COLOR = 1
STATE_ASK_LEVEL = 2
STATE_ASK_ANALYZE = 3
STATE_PLAY = 4
STATE_END_PLAY = 5
STATE_ANALYZE_ASK_FINISH = 6
STATE_ANALYSIS0 = 0x10
STATE_ANALYSIS1 = 0x11
STATE_ANALYSIS2 = 0x12
STATE_ANALYSIS3 = 0x13
STATE_ANALYSIS4 = 0x14
STATE_ANALYSIS5 = 0x15
MASK_ANALYSIS = 0x10

OPTIONS = {
    STATE_ASK_PLAY: (ord('y'),ord('n')),
    STATE_ANALYZE_ASK_FINISH: (ord('y'),ord('n')),
    STATE_ASK_COLOR: (ord('w'),ord('b')),
    STATE_ASK_LEVEL: (ord('1'),ord('2'),ord('3'),ord('4'),ord('5'),ord('6')),
    STATE_ASK_ANALYZE: (ord('y'),ord('n')),
    STATE_ANALYSIS1: tuple(map(ord,'kqrbnp.')),
    STATE_ANALYSIS3: (ord('w'),ord('b')),
    STATE_ANALYSIS5: (ord('1'),ord('0'))
}

HEXFILE = "zout/sargon-z80.hex"
LSTFILE = "zout/sargon-z80.lst"

locations = readlst.getSymbols(LSTFILE)

START = locations['DRIVER']
BLINKER = locations['BL10']-3
BOARD = locations['BOARDA']
ANBDPS = locations['ANBDPS']

if CHECK_FOR_COMPUTER_REPEATS:
    COMPUTER_MOVE = locations['CPTRMV'] 
    AFTER_MOVE = locations['CP0C']+6 
    POINTS = locations['POINTS'] 
    POINTS_END = locations['rel016'] 
    COMPUTER_COLOR = locations['KOLOR'] 
    CURRENT_COLOR = locations['COLOR'] 

state = STATE_ASK_PLAY
repeatRun = False

JUPITER_SCREEN = 0xC000
JUPITER_WIDTH = 64
JUPITER_LEFT_SIDE = 16
JUPITER_HEIGHT = 32
VCHAR = ZOOM*3
HCHAR = ZOOM*2
SQUARE = ZOOM*12

KEY_LEFT = (65361,2424832)
KEY_RIGHT = (65363,2555904)
KEY_UP = (65362,2490368)
KEY_DOWN = (65364,2621440)
KEY_SELECT = (10,13)
KEY_ARROWS = KEY_LEFT+KEY_RIGHT+KEY_UP+KEY_DOWN

usedArrows = False

cursorX = 0
cursorY = 0

boardCursorX = None
boardCursorY = None

keyfeed = ''
moveFrom = True

def makeMove(col,row):
    global keyfeed,moveFrom
    keyfeed += chr(col+ord('a')) + chr(row+ord('1'))
    if moveFrom:
        keyfeed += '-'
    moveFrom = not moveFrom

def mouseClick(event,x,y,flags,param):
    if event == cv2.EVENT_LBUTTONDOWN:
        left = (JUPITER_WIDTH*2-12*8)*ZOOM
        if x >= left:
            col = (x - left) // SQUARE
            row = 7 - y // SQUARE
            if 0 <= col <= 7 and 0 <= row <= 7:
                makeMove(col,row)
            
cv2.namedWindow(WINDOW)
cv2.setMouseCallback(WINDOW,mouseClick)

def updateScreen():
    cv2.imshow(WINDOW, getImage())

def getch():
    global keyfeed, boardCursorX, boardCursorY, usedArrows, state
    
    if state & MASK_ANALYSIS:
        state += 1
    
    if state in OPTIONS:
        putCharacter(OPTIONS[state][0], advance=False)
        updateScreen()
    
    while True:
        if keyfeed:
            c = keyfeed[0]
            keyfeed = keyfeed[1:]
            return c
        if cv2.getWindowProperty(WINDOW, 0) == -1:
            sys.exit(0)
        c = cv2.waitKeyEx(1)
        if c < 0:
            continue
        if not usedArrows and c in KEY_ARROWS:
            usedArrows = True
        if c == 27 and state & MASK_ANALYSIS == 0:
            if state in OPTIONS and ord('n') in OPTIONS[state]:
                return 'n'
            c = 18
        if c in KEY_SELECT and state in OPTIONS and ord('n') in OPTIONS[state] and len(OPTIONS[state]) == 2:
            pressed = getCharacter() 
            if pressed in OPTIONS[state]:
                return chr(pressed)
            else:
                return 'y'

        if state == STATE_PLAY:
            if boardCursorX == None:
                boardCursorX = 3
                boardCursorY = 3
            if c in KEY_LEFT:
                boardCursorX = (boardCursorX + 7) % 8
                updateScreen()
                c = -1
            elif c in KEY_RIGHT:
                boardCursorX = (boardCursorX + 1) % 8
                updateScreen()
                c = -1
            elif c in KEY_UP:
                boardCursorY = (boardCursorY + 7) % 8
                updateScreen()
                c = -1
            elif c in KEY_DOWN:
                boardCursorY = (boardCursorY + 1) % 8
                updateScreen()
                c = -1
            elif c in KEY_SELECT:
                makeMove(boardCursorX, 7-boardCursorY)
                c = -1
        elif state in OPTIONS:
            options = OPTIONS[state]
            if state == STATE_ANALYSIS1 and c in KEY_LEFT+KEY_RIGHT:
                if c in KEY_LEFT:
                    return '\x08'
                else:
                    return '\r'
            elif c in KEY_DOWN+KEY_UP:
                current = getCharacter()
                try:
                    index = options.index(current)
                    if c in KEY_DOWN:
                        index = (len(options)+index-1) % len(options)
                    else:
                        index = (index+1) % len(options)
                except:
                    index = 0
                putCharacter(options[index], advance=False)
                updateScreen()
                c = -1
            elif c in KEY_SELECT and (state & MASK_ANALYSIS == 0 or usedArrows):
                current = getCharacter()
                if current in options:
                    if (state == STATE_ANALYSIS1 and current != ord('.')) or state == STATE_ANALYSIS3:
                        keyfeed = '\r' 
                    return chr(current)
            elif c == 27 and (ord('n') in options and (state & MASK_ANALYSIS == 0)):
                return 'n'

        if c >= 0 and c < 0x100:
            return chr(c)
        
charset = []

for i in range(256):
    data = np.zeros((VCHAR,HCHAR),dtype=np.uint8)
    data.fill(255)
    for start,end in hp1345.hp1345_render(chr(i), width=HCHAR, round=round, dotSize=0):
        if ZOOM>8:
            cv2.line(data, start, end, 0, 2, cv2.LINE_AA)
        else:
            cv2.line(data, start, end, 0, 1)
    charset.append(data)

blocks = []

for block in range(64):
    data = np.zeros((3,2),dtype=np.uint8)
    a = 1
    for j in range(3):
        for i in range(2):
            data[j,i] = 0 if (block & a) else 255
            a <<= 1
    blocks.append(data)

def getWord(address):
    return z.memory[address] | (z.memory[(address+1) & 0xFFFF] << 8)

def setWord(address,data):
    z.memory[address] = data & 0xFF
    z.memory[(address+1) & 0xFFFF] = data >> 8
    
def getBytes(address,count):
    data = bytearray(count)
    for i in range(count):
        data[i] = z.memory[(address+i)&0xFFFF]
    return data
    
def putCharacter(c, advance=True):
    global cursorX, cursorY
    if c == ord('\n'):
        if advance:
            cursorY += 1
            cursorX = 0
            if cursorY >= JUPITER_HEIGHT:
                cursorY = JUPITER_HEIGHT - 1
    elif c >= 32:
        z.memory[JUPITER_SCREEN+cursorY*JUPITER_WIDTH+cursorX] = c
        if advance:
            cursorX += 1
                        
def getCharacter():
    return z.memory[JUPITER_SCREEN+cursorY*JUPITER_WIDTH+cursorX]

def clearScreen():            
    global cursorX, cursorY
    cursorX = 0
    cursorY = 0
    for i in range(JUPITER_WIDTH*JUPITER_HEIGHT):
        z.memory[JUPITER_SCREEN+i] = 0
        
def updateState(msg):
    global state, computerHistory
    s = msg.decode("ascii", "ignore")
    if 'CARE FOR' in s:
        state = STATE_ASK_PLAY
    elif 'IS THIS RIGHT' in s:
        state = STATE_ANALYZE_ASK_FINISH
    elif 'LIKE TO ANALYZE' in s:
        state = STATE_ASK_ANALYZE
    elif 'DO YOU WANT TO PLAY' in s or 'WHOSE MOVE' in s:
        state = STATE_ASK_COLOR
    elif 'LOOK AHEAD' in s:
        state = STATE_ASK_LEVEL
    elif 'SARGON' in s:
        state = STATE_PLAY
    if CHECK_FOR_COMPUTER_REPEATS and state != STATE_PLAY:
        computerHistory = []
        repeatRun = False
            
def handle38():
    global state
    addr = getWord(z.sp)
    function1 = z.memory[addr]
    addr = (addr+1) & 0xFFFF
    function2 = z.memory[addr]
    addr = (addr+1) & 0xFFFF
    if (function1 == 0xb2 or function1 == 0xb3) and function2 == 0x1a:
        msg = getWord(addr)
        addr = (addr+2) & 0xFFFF
        length = getWord(addr)
        addr = (addr+2) & 0xFFFF
        pos = msg
        updateState(getBytes(msg, length))
        while length:
            c = z.memory[pos]
            if c == ord('['):
                c = z.memory[pos+1]
                pos += 2
                if c == 0x1c:
                    if state == STATE_ANALYZE_ASK_FINISH:
                        state = STATE_ANALYSIS0
                    clearScreen()
                elif c == 0x83:
                    putCharacter(ord('-'))
            else:
                putCharacter(c)
            pos += 1
            length -= 1
        if function1 != 0xb3:
            putCharacter(ord('\n'))
    elif function1 == 0x92 and function2 == 0x1a:
        addr = (addr+2) & 0xFFFF
        putCharacter(ord('\n'))
    elif function1 == 0x81 and function2 == 0x00:
        c = getch()
        if state == STATE_ASK_ANALYZE and c in ('y','Y'):
            state = STATE_ANALYSIS0
        z.a = ord(c)
        
    elif function1 == 0x81 and function2 == 0x1A:
        putCharacter(z.a)
    elif function1 == 0x1F:
        print("[done]")
        return True
    else:
        print("Unknown function 0x%02x from 0x%04x" % (function1,addr-4))
        
    z.sp += 2
    z.pc = addr
    return False

z = z80.Z80Machine()
z.set_memory_block(0, readhex.hexToMemory(HEXFILE))
z.set_breakpoint(0x38)
z.set_breakpoint(0x00)
z.set_breakpoint(BLINKER) 
if CHECK_FOR_COMPUTER_REPEATS:
    #z.set_breakpoint(COMPUTER_MOVE)
    z.set_breakpoint(AFTER_MOVE)
z.pc = START

def getImage():
    screen = np.full((JUPITER_HEIGHT*VCHAR,JUPITER_WIDTH*HCHAR),255,dtype=np.uint8)
    right = np.full((JUPITER_HEIGHT*3,(JUPITER_WIDTH-JUPITER_LEFT_SIDE)*2),255,dtype=np.uint8)
    
    haveBlocks = False
    for x in range(JUPITER_LEFT_SIDE,JUPITER_WIDTH):
        for y in range(JUPITER_HEIGHT):
            c = z.memory[JUPITER_SCREEN + y * JUPITER_WIDTH + x]
            if 0x80 <= c < 0x80 + 64:
                x1 = (x-JUPITER_LEFT_SIDE)*2
                y1 = y*3
                right[y1:y1+3, x1:x1+2] = blocks[c-0x80]
                haveBlocks = True

    if FLOODFILL and haveBlocks:
        for col in range(8):
            for row in range(8):
                chunk = right[12*row:12*(row+1), 12*col:12*(col+1)]
                cv2.floodFill(chunk,None,(0,0),64 if chunk[0,0] == 0 else 192)
                right[12*row:12*(row+1), 12*col:12*(col+1)] = chunk
            
    screen[0:JUPITER_HEIGHT*VCHAR,JUPITER_LEFT_SIDE*HCHAR:JUPITER_WIDTH*HCHAR] = cv2.resize(right, (HCHAR*(JUPITER_WIDTH-JUPITER_LEFT_SIDE),VCHAR*JUPITER_HEIGHT), interpolation = cv2.INTER_NEAREST)
        
    for x in range(JUPITER_WIDTH):
        for y in range(JUPITER_HEIGHT):
            c = z.memory[JUPITER_SCREEN + y * JUPITER_WIDTH + x]
            if c < 0x80:
                x1 = x*HCHAR
                y1 = y*VCHAR
                screen[y1:y1+VCHAR, x1:x1+HCHAR] = charset[c]
                
    x = None
    
    if state == STATE_PLAY and boardCursorX is not None and boardCursorY is not None and usedArrows:
        x = boardCursorX 
        y = boardCursorY 
        
    if (state & MASK_ANALYSIS) and z.memory[ANBDPS]:
        x = (z.memory[ANBDPS] % 10) - 1
        y = 7 - ((z.memory[ANBDPS] // 10) - 2)

    if x is not None:
        x = x * SQUARE + JUPITER_LEFT_SIDE*HCHAR + SQUARE // 2
        y = y * SQUARE + SQUARE // 2
        cv2.circle(screen, (x,y), int(SQUARE * 0.45), 0 if (x+y)%2 == 0 else 255, 2, cv2.LINE_AA)
        
    return screen
    
def signed(x):
    return x - 256 if x >= 128 else x

def handleBreakpoints():
    global repeatRun, state
    
    if z.pc == 0x00:
        print("[reset]")
        return True
    elif z.pc == 0x38:
        return handle38()
    elif z.pc == BLINKER:
        if state & MASK_ANALYSIS:
            state = STATE_ANALYSIS0
        time.sleep(0.002)
    elif CHECK_FOR_COMPUTER_REPEATS:
        if z.pc == AFTER_MOVE:
            board = bytes(z.memory[BOARD:BOARD+120])
            count = computerHistory.count(board)
            if count >= 2:
                if repeatRun:
                    print("I declare a draw!")
                    z.clear_breakpoint(POINTS)
                    repeatRun = False
                else:
                    print("recomputing to avoid draw")
                    z.set_breakpoint(POINTS)
                    z.pc = COMPUTER_MOVE
                    repeatRun = True
            if z.pc == AFTER_MOVE:
                computerHistory.append(board)
        elif z.pc == POINTS:
            board = bytes(z.memory[BOARD:BOARD+120])
            if z.memory[COMPUTER_COLOR] == z.memory[CURRENT_COLOR] and computerHistory.count(board) >= 2:
                z.a = 0
                z.pc = POINTS_END
    else:
        history.append(board)
    return False    

lastFrame = 0
while True:
    z.ticks_to_stop = 200000
    events = z.run()
    if (events & z._BREAKPOINT_HIT) or time.time() >= lastFrame + MINIMUM_COMPUTE_TIME_PER_FRAME:
        updateScreen()
        if handleBreakpoints():
            break
        cv2.waitKey(1)
        if cv2.getWindowProperty(WINDOW, 0) == -1:
            break

        lastFrame = time.time()
