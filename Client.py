from tkinter import *
import tkinter.messagebox
from PIL import Image, ImageTk
import socket
import threading
import sys
import traceback
import os
import time

from RtpPacket import RtpPacket

CACHE_FILE_NAME = "cache-"
CACHE_FILE_EXT = ".jpg"


class Client:
    INIT = 0
    READY = 1
    PLAYING = 2
    state = INIT

    SETUP = 0
    PLAY = 1
    PAUSE = 2
    TEARDOWN = 3
    OPTIONS = 4
    DESCRIBE = 5

    # Initiation..
    def __init__(self, master, serveraddr, serverport, rtpport, filename):
        self.master = master
        self.master.protocol("WM_DELETE_WINDOW", self.handler)
        self.createWidgets()
        self.serverAddr = serveraddr
        self.serverPort = int(serverport)
        self.rtpPort = int(rtpport)
        self.fileName = filename
        self.rtspSeq = 0
        self.sessionId = 0
        self.requestSent = -1
        self.teardownAcked = 0
        self.connectToServer()
        self.frameNbr = 0

    def createWidgets(self):
        """Build GUI."""
        # Create Setup button
        # self.setup = Button(self.master, width=20, padx=3, pady=3)
        # self.setup["text"] = "Setup"
        # self.setup["command"] = self.setupMovie
        # self.setup.grid(row=1, column=0, padx=2, pady=2)

        # Create Option button
        self.option = Button(self.master, width=20, padx=3, pady=3)
        self.option["text"] = "Option"
        self.option["command"] = self.sendOptionsRequest
        self.option.grid(row=1, column=0, padx=2, pady=2)

        # Create Describe button
        self.describe = Button(self.master, width=20, padx=3, pady=3)
        self.describe["text"] = "Describe"
        self.describe["command"] = self.sendDescribeRequest
        self.describe.grid(row=1, column=1, padx=2, pady=2)

        # Create Play button
        self.start = Button(self.master, width=20, padx=3, pady=3)
        self.start["text"] = "Play"
        self.start["command"] = self.playMovie
        self.start.grid(row=1, column=2, padx=2, pady=2)

        # Create Pause button
        self.pause = Button(self.master, width=20, padx=3, pady=3)
        self.pause["text"] = "Pause"
        self.pause["command"] = self.pauseMovie
        self.pause.grid(row=1, column=3, padx=2, pady=2)

        # Create Teardown button
        self.teardown = Button(self.master, width=20, padx=3, pady=3)
        self.teardown["text"] = "Teardown"
        self.teardown["command"] = self.exitClient
        self.teardown.grid(row=1, column=4, padx=2, pady=2)

        # Create a label to display the movie
        self.label = Label(self.master, height=19)
        self.label.grid(row=0, column=0, columnspan=4,
                        sticky=W+E+N+S, padx=5, pady=5)

        # FIX: call function
        self.changeStatusButton()

    def setupMovie(self):
        """Setup button handler."""
        if self.state == self.INIT:
            self.sendRtspRequest(self.SETUP)


    def exitClient(self):
        """Teardown button handler."""
        self.sendRtspRequest(self.TEARDOWN)
        self.master.destroy()  # Close the gui window
        # Delete the cache image from video
        fullFileName = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        # FIX: add os.path.exists() to check file exist or not
        if (os.path.exists(fullFileName)):
            os.remove(fullFileName)

    def pauseMovie(self):
        """Pause button handler."""
        if self.state == self.PLAYING:
            self.sendRtspRequest(self.PAUSE)

    def sendOptionsRequest(self):
        self.sendRtspRequest(self.OPTIONS)

    def sendDescribeRequest(self):
        self.sendRtspRequest(self.DESCRIBE)

    def playMovie(self):
        """Play button handler."""
        if self.state == self.READY:
            # Create a new thread to listen for RTP packets
            threading.Thread(target=self.listenRtp).start()
            self.playEvent = threading.Event()
            self.playEvent.clear()
            self.sendRtspRequest(self.PLAY)

    def listenRtp(self):
        """Listen for RTP packets."""
        while True:
            try:
                data = self.rtpSocket.recv(20480)
                self.rtpSocket.settimeout(0.5)
                if data:
                    rtpPacket = RtpPacket()
                    rtpPacket.decode(data)

                    currFrameNbr = rtpPacket.seqNum()
                    print("Current Seq Num: " + str(currFrameNbr))

                    if currFrameNbr > self.frameNbr:  # Discard the late packet
                        self.frameNbr = currFrameNbr
                        # FIX: add condition
                        if (self.requestSent != self.TEARDOWN):
                            self.updateMovie(self.writeFrame(
                                rtpPacket.getPayload()))
                        else:
                            break
            except:
                # Stop listening upon requesting PAUSE or TEARDOWN
                if self.playEvent.isSet():
                    break

                # Upon receiving ACK for TEARDOWN request,
                # close the RTP socket
                if self.teardownAcked == 1:
                    self.rtpSocket.shutdown(socket.SHUT_RDWR)
                    self.rtpSocket.close()
                    break

                if (self.frameNbr == 0):
                    tkinter.messagebox.showwarning("File not found", "Can not find " + self.fileName)
                    break

    def writeFrame(self, data):
        """Write the received frame to a temp image file. Return the image file."""
        cachename = CACHE_FILE_NAME + str(self.sessionId) + CACHE_FILE_EXT
        file = open(cachename, "wb")
        file.write(data)
        file.close()

        return cachename

    def updateMovie(self, imageFile):
        """Update the image file as video frame in the GUI."""
        photo = ImageTk.PhotoImage(Image.open(imageFile))
        self.label.configure(image=photo, height=288)
        self.label.image = photo

    def connectToServer(self):
        """Connect to the Server. Start a new RTSP/TCP session."""
        self.rtspSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.rtspSocket.connect((self.serverAddr, self.serverPort))
            self.setupMovie()
        except:
            tkinter.messagebox.showwarning(
                'Connection Failed', 'Connection to \'%s\' failed.' % self.serverAddr)

    def sendRtspRequest(self, requestCode):
        """Send RTSP request to the server."""
        # -------------
        # TO COMPLETE
        # -------------

        # Setup request
        if requestCode == self.SETUP and self.state == self.INIT:
            threading.Thread(target=self.recvRtspReply).start()
            # Update RTSP sequence number.
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            # request = ...
            request = "SETUP " + self.fileName + " RTSP/1.0\nCSeq: " + \
                str(self.rtspSeq) + \
                "\nTransport: RTP/UDP; client_port= " + str(self.rtpPort)
            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.SETUP

        # Play request
        elif requestCode == self.PLAY and self.state == self.READY:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            # request = ...
            request = "PLAY " + self.fileName + " RTSP/1.0\nCSeq: " + \
                str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.PLAY

        # Pause request
        elif requestCode == self.PAUSE and self.state == self.PLAYING:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            # request = ...
            request = "PAUSE " + self.fileName + " RTSP/1.0\nCSeq: " + \
                str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.PAUSE

        # Teardown request
        elif requestCode == self.TEARDOWN and not self.state == self.INIT:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            # request = ...
            request = "TEARDOWN " + self.fileName + " RTSP/1.0\nCSeq: " + \
                str(self.rtspSeq) + "\nSession: " + str(self.sessionId)
            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.TEARDOWN

        elif requestCode == self.OPTIONS:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            # request = ...
            request = "OPTIONS " + self.fileName + " RTSP/1.0\nCSeq: " + \
                str(self.rtspSeq) + "\nRequire: " + "implicit-play"
            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.OPTIONS
            
        elif requestCode == self.DESCRIBE:
            # Update RTSP sequence number.
            self.rtspSeq += 1
            # Write the RTSP request to be sent.
            # request = ...
            request = "DESCRIBE " + self.fileName + " RTSP/1.0\nCSeq: " + \
                str(self.rtspSeq) + "\nAccept: application/sdp, application/rtsl, application/mheg"
            # Keep track of the sent request.
            # self.requestSent = ...
            self.requestSent = self.DESCRIBE
        else:
            return

        # Send the RTSP request using rtspSocket.
        self.rtspSocket.send(request.encode("utf-8"))
        print('\nData sent:\n' + request)

    def recvRtspReply(self):
        """Receive RTSP reply from the server."""
        while True:
            reply = self.rtspSocket.recv(1024)
        
            if reply:
                self.parseRtspReply(reply.decode("utf-8"))

            # Close the RTSP socket upon requesting Teardown
            if self.requestSent == self.TEARDOWN:
                self.rtspSocket.shutdown(socket.SHUT_RDWR)
                self.rtspSocket.close()
                break

    def parseRtspReply(self, data):
        """Parse the RTSP reply from the server."""
        lines = data.split('\n')
        seqNum = int(lines[1].split(' ')[1])

        # Process only if the server reply's sequence number is the same as the request's
        if seqNum == self.rtspSeq:
            if self.requestSent == self.OPTIONS:
                print(data)
            elif self.requestSent == self.DESCRIBE:
                print(data)
            else:
                session = int(lines[2].split(' ')[1])
                # New RTSP session ID
                if self.sessionId == 0:
                    self.sessionId = session

                # Process only if the session ID is the same
                if self.sessionId == session:
                    if int(lines[0].split(' ')[1]) == 200:
                        if self.requestSent == self.SETUP:
                            # -------------
                            # TO COMPLETE
                            # -------------
                            # Update RTSP state.
                            # self.state = ...
                            self.state = self.READY
                            # Open RTP port.
                            self.openRtpPort()

                        elif self.requestSent == self.PLAY:
                            # self.state = ...
                            self.state = self.PLAYING
                        elif self.requestSent == self.PAUSE:
                            # self.state = ...
                            self.state = self.READY
                            # The play thread exits. A new thread is created on resume.
                            self.playEvent.set()
                        elif self.requestSent == self.TEARDOWN:
                            # self.state = ...
                            self.state = self.INIT
                            # Flag the teardownAcked to close the socket.
                            self.teardownAcked = 1

                        # FIX: call function
                        if (self.teardownAcked == 0):
                            self.changeStatusButton()

    def openRtpPort(self):
        """Open RTP socket binded to a specified port."""
        # -------------
        # TO COMPLETE
        # -------------
        # Create a new datagram socket to receive RTP packets from the server
        # self.rtpSocket = ...
        self.rtpSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set the timeout value of the socket to 0.5sec
        self.rtpSocket.settimeout(0.5)

        try:
            # Bind the socket to the address using the RTP port given by the client user
            self.rtpSocket.bind((self.serverAddr, self.rtpPort))
        except:
            tkinter.messagebox.showwarning(
                'Unable to Bind', 'Unable to bind PORT=%d' % self.rtpPort)

    def handler(self):
        """Handler on explicitly closing the GUI window."""
        self.pauseMovie()
        if tkinter.messagebox.askokcancel("Quit?", "Are you sure you want to quit?"):
            self.exitClient()
        else:  # When the user presses cancel, resume playing.
            # FIX: can not resume if not begin yet
            if (self.frameNbr > 0):
                self.playMovie()

    # FIX: add disable status for button
    def changeStatusButton(self):
        if self.state == self.INIT:
            # self.setup['state'] = NORMAL
            self.start['state'] = DISABLED
            self.pause['state'] = DISABLED
            self.teardown['state'] = DISABLED
        elif self.state == self.READY:
            # self.setup['state'] = DISABLED
            self.start['state'] = NORMAL
            self.pause['state'] = DISABLED
            self.teardown['state'] = NORMAL
        elif self.state == self.PLAYING:
            # self.setup['state'] = DISABLED
            self.start['state'] = DISABLED
            self.pause['state'] = NORMAL
            self.teardown['state'] = NORMAL