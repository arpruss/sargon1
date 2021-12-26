This is a python wrapper emulator for Sargon I. All the python code here is public domain,
except perhaps the hp1345 font, whose copyright status, if any, I do not know.

It requires zout/sargon-z80.lst and zout/sargon-z80.hex generated via zmac from sargon-z80.asm
(google it). I recommend patching sargon-z80.asm using the provided patch in the sargon-z80.asm.diff
file to fix a scan error and some bugs in the original code: 
 
 - data overlap bug 
 
 - movement bugs in analysis mode
 
 - bug when analysis mode is invoked at game start.

sargon-text.py is a very simple text mode emulator. 

sargon.py is a more complex emulator using openCV for graphics, and having the python code check
for repeated computer board positions to avoid Sargon's penchant for repeating moves in the 
endgame.

You will need:

 - OpenCV2: python3 -m pip install opencv-python
 
 - Kosarev's Z80 emulator as modified by me: Download from https://github.com/arpruss/z80 ,
   go to its z80 directory and do python3 setup.py install
   
 - py-getch for the text-mode script: python3 -m pip install py-getch
    