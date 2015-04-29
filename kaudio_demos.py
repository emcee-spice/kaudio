#!/usr/bin/python

from kaudio import *
import time
import math

init()

A7_freqs = [220, 554, 659, 784]

def overtone_demo():
    note_freqs = {
        'a' : 440.000,
        'b' : 493.883,
        'c' : 523.251,
        'd' : 587.330,
        'e' : 659.255,
        'f' : 698.456,
        'g' : 783.991
    }
    freq = None
    while True:
        s = raw_input('Enter a note A through G: ').lower()
        if len(s) == 1 and 'a' <= s <= 'g':
            freq = note_freqs[s]
            break
        else:
            print 'Invalid input.'
    series_signal = CompositeSignal(Wave(WaveType.SINE, int(freq), 8000))
    series_signal.play()
    overtone = 0
    while True:
        t = raw_input('Enter "q" to quit, or anything else to play the next overtone: ')
        if t.lower() == 'q':
            break
        else:
            overtone += 1
            freq += freq / overtone
            series_signal.add_signal(Wave(WaveType.SINE, int(freq), 8000))
    series_signal.pause()

def fader_shift(comp_fader):
    i = 0
    while True:
        time.sleep(0.1)
        balance  = (math.sin(2 * math.pi * i / 40.0) + 1) / 2.0
        comp_fader.l_to_l = balance
        comp_fader.l_to_r = 1 - balance
        comp_fader.r_to_l = 1 - balance
        comp_fader.r_to_r = balance
        i += 1
        if i >= 40: i = 0

def fader_shift_demo():
    girl_talk = SignalFromAudioFile('girl-talk.wav', loop=True)
    girl_talk.add_effect(Fader(1, 0))
    guy_talk  = SignalFromAudioFile('guy-talk.wav',  loop=True)
    guy_talk.add_effect(Fader(0, 1))
    both_talk = CompositeSignal(girl_talk, guy_talk)
    both_talk.play()
    comp_fader = ComplexFader(1, 0, 0, 1)
    both_talk.add_effect(comp_fader)
    fader_shift(comp_fader)

def guitar_demo():
    signal = SignalFromAudioFile('guitar.wav', loop=True)
    signal.play()
    raw_input("press ENTER to compress ")
    comp = Compressor(3000, 1, 3000, 3)
    amp = Amplifier(1)
    signal.add_effect(amp)
    raw_input("press ENTER to oscillate ")
    signal.remove_effect(comp)
    signal.remove_effect(amp)
    osc = Oscillator(15, 2)
    signal.add_effect(osc)
    raw_input("press ENTER to overdrive ")
    signal.remove_effect(osc)
    signal.add_effect(Overdriver(4, 8000))
    raw_input("press ENTER to quit ")
    signal.pause()

def wave_gen_test():
    signals = [Wave(WaveType.SINE, 440, 8000),
               Wave(WaveType.SQUARE, 440, 8000),
               Wave(WaveType.TRIANGLE, 440, 8000),
               Wave(WaveType.SAWTOOTH, 440, 8000)]
    for s in signals:
        s.play()
        time.sleep(3)
        s.pause()

def wav_file_test():
    signal = SignalFromAudioFile('test.wav', loop=True)
    signal.play()
    raw_input("press ENTER to amplify ")
    amp = Amplifier(3)
    signal.add_effect(amp)
    raw_input("press ENTER again to switch channels")
    fader = ComplexFader(0, 1, 1, 0)
    signal.add_effect(fader)
    raw_input("press ENTER again to make mono ")
    fader2 = ComplexFader(0.5, 0.5, 0.5, 0.5)
    signal.add_effect(fader2)
    raw_input("press ENTER again to quit ")
    signal.pause()

print 'Edit this line of code to call one of the demo functions'
