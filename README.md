What this is
============
A command-line driver/tool for the USB IR-Toy, written in python.


What you will need
==================

An IR-Toy, obviously ;-) http://dangerousprototypes.com/docs/USB_IR_Toy_v2

 - Python >= 3.2
  > See http://www.python.org/download/releases/
  - Ubuntu: `sudo apt-get install python3`
  
 - PySerial (for Python 3)
  > See http://pyserial.sourceforge.net/pyserial.html#installation
   - Ubuntu: `sudo apt-get install python3-serial`

Both pakages are avaible for Linux and Windows


How to install
==============
Download the source into a directory of your choice.

Open a terminal, navigate to this directory and run

Windows: `python3 irtoy.py --help`

Linux: `chmod +x irtoy.py; ./irtoy.py --help`



Examples
=========
For Windows, add `--device=COM1` to the parameters
### Record an IR stream to file "out.bin"
    irtoy.py record out.bin


### Play a raw IR stream from file "input.bin"
    irtoy.py play input.bin



MACRO FEATURE
================
Similar to LIRC, you can use this tool as an universal remote control! (not all remote control protocols supported currently)

##Step 1: Scan the buttons on the remote control and give them names
    irtoy.py buttons button_file.rcb
Then follow the instructions. This will create a _button map file_.

### Example
```shell
~$ irtoy.py buttons tv_control.rcb
Open and reset device... 
Done.

Please press a button on the remote
Addr: 0x15 Cmd: 0x25
Name of the button: volumeUp
Record more? [Y/n] y
Please press a button on the remote
Addr: 0x15 Cmd: 0x26
Name of the button: volumeDown
Record more? [Y/n] y
Please press a button on the remote
...
...
...
Record more? [Y/n] n
File tv_control.rcb written
```

Now you have a file named `tv_control.rcb`, the _"button map"_ for your TV remote control!



##Step 2: Playing a macro
    irtoy.py macro "macro script here, see below" button_file.rcb
    
###Macro syntax
A macro is a string witch represents a series of keystrokes on a remote control and idle times.

A **keystroke** is represented by the **name** (that you entered for this key when creating 
the button map file, e.g. "volumeUp") and optionally followed by a **colon** with the **duration**
the key should remain pressed:

    btnName[:Time]

**Time format**: `N_units` (N is a number, units is one of 'ms', 's', 'm', 'h')

###Examples for keystrokes: 
 * `powerOn` (simply press the button named "powerOn" once)
 * `volumeUp:500_ms` (hold down the "volumeUp" button for 500 milliseconds)

The syntax for **idle times** between two keystrokes is:

    .Time
where `Time` is in the time format as above.

Idle times and keystrokes are separated by **spaces**.

##Examples for Macros

Task: "press the button named _'power'_, then hold the _'volumeUp'_ button for one second,  then _wait two minutes_ and press the _'power'_ button again using _tv_control.rcb_ as button map file"
 
    irtoy.py macro "power volumeUp:1_s .2_m power" tv_control.rcb
