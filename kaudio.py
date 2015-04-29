# Kyle McCormick
# 2015-04-29



################################################################################
# GENERAL
################################################################################

import pyaudio
import wave
import math
import numpy
import struct
import threading
import time

pa = None
chunk_size = 512

def init():
    global pa
    assert pa is None
    pa = pyaudio.PyAudio()

def terminate():
    global pa
    if pa:
        pa.terminate()
        pa = None

def set_chunk_size(val):
    assert val > 0
    global chunk_size
    chunk_size = val

class LibraryError(Exception):
    pass




################################################################################
# SIGNALS
################################################################################

class Signal(object):
    def __init__(self, frame_rate, loop):
        assert frame_rate > 0
        self.frame_rate = frame_rate
        self.loop = loop
        self._is_playing = False
        self._stop_requested = False
        self._effects = []
    def play(self):
        th = threading.Thread(target=self._play_loop, args=())
        self._stop_requested = False
        th.start()
    def play_and_wait(self):
        self.play()
        while self._is_playing:
            time.sleep(0.001)
    def pause(self):
        self._stop_requested = True
        while self._is_playing:
            time.sleep(0.001)
    def is_playing(self):
        return self._is_playing
    def rewind(self):
        raise LibraryError('Signal subclass failed to override rewind')
    def add_effect(self, e):
        self._effects.append(e)
    def remove_effect(self, e):
        if self._effects.count(e) > 0:
            self._effects.remove(e)
    def _play_loop(self):
        self._is_playing = True
        stream = pa.open(format=pyaudio.paInt16,
                         channels=2,
                         rate=self.frame_rate,
                         output=True)
        left, right = numpy.zeros((chunk_size,), dtype=numpy.int16), \
                      numpy.zeros((chunk_size,), dtype=numpy.int16)
        has_more_data = self._get_samples(left, right)
        while has_more_data and not self._stop_requested:
            for i in range(0, len(left)):
                for e in self._effects:
                    e.apply_to_samples(i, left, right, self.frame_rate)
            data = ''
            for f in range(0, left.shape[0]):
                data += struct.pack('h', left[f])
                data += struct.pack('h', right[f])
            stream.write(data)
            left [range(0, chunk_size)] = 0
            right[range(0, chunk_size)] = 0
            has_more_data = self._get_samples(left, right)
        stream.stop_stream()
        stream.close()
        self._is_playing = False
    def _get_samples(self, left, right):
        raise LibraryError('Signal subclass failed to override _get_samples')

class SignalFromAudioFile(Signal):
    def __init__(self, fpath, loop=False):
        assert fpath != None
        self._infile = wave.open(fpath, 'rb')
        Signal.__init__(self, self._infile.getframerate(), loop)
        fmt = pa.get_format_from_width(self._infile.getsampwidth())
        if fmt != pyaudio.paInt16:
            raise IOError('can only load files with 16-bit integer encoding')
        self._num_chans = self._infile.getnchannels()
        if not self._num_chans in [1, 2]:
            raise IOError('can only load files with 1 or 2 channels')
        self._is_rewinding = False
        self._fpath = fpath
    def rewind(self):
        self._is_rewinding = True
        if self._infile:
            self._infile.close()
        self._infile = wave.open(self._fpath, 'rb')
        self._is_rewinding = False
    def _get_samples(self, left, right):
        if self._is_rewinding:
            return
        data = self._infile.readframes(left.shape[0])
        if data == '':
            if self.loop:
                self.rewind()
                data = self._infile.readframes(left.shape[0])
            else:
                self._infile.close()
                self._infile = None
                return None
        frames_read = len(data) / 2 / self._num_chans
        for ix_frame in range(0, frames_read):
            ix_sample = ix_frame * self._num_chans
            str1 = data[ix_sample*2+0] + data[ix_sample*2+1]
            val1 = struct.unpack('h', str1)[0]
            left[ix_frame] = val1
            if self._num_chans == 1:
                right[ix_frame] = val1
            else:
                str2 = data[ix_sample*2+2] + data[ix_sample*2+3]
                val2 = struct.unpack('h', str2)[0]
                right[ix_frame] = val2
        return frames_read > 0

class WaveType(object):
    SINE = 0
    SQUARE = 1
    TRIANGLE = 2
    SAWTOOTH = 3
    _MIN = SINE
    _MAX = SAWTOOTH

class Wave(Signal):
    def __init__(self, wave_type, freq, amplitude, loop=True):
        Signal.__init__(self, 44100, loop)
        assert WaveType._MIN <= wave_type <= WaveType._MAX
        assert freq > 0
        self.wave_type = wave_type
        self.freq = freq
        self.amplitude = amplitude
        self._frames_per_cycle = self.frame_rate / self.freq
        self._ix_frame = 0
    def rewind(self):
        self._ix_frame = 0
    def _calc_sample_val(self):
        d = self._ix_frame / float(self._frames_per_cycle)
        val = None
        if self.wave_type == WaveType.SINE:
            val = math.sin(2 * math.pi * d)
        elif self.wave_type == WaveType.SQUARE:
            val = (1 if d < 0.5 else -1)
        elif self.wave_type == WaveType.TRIANGLE:
            val = (d if d < 0.5 else (1 - d)) * 4 - 1
        elif self.wave_type == WaveType.SAWTOOTH:
            val = d * 2 - 1
        return self.amplitude * val
    def _get_samples(self, left, right):
        for i in range(0, left.shape[0]):
            left[i] = right[i] = self._calc_sample_val()
            self._ix_frame += 1
            if self._ix_frame >= self._frames_per_cycle:
                if self.loop:
                    self._ix_frame = 0
                else:
                    return False
        return True

class CompositeSignal(Signal):
    def __init__(self, *signals):
        assert len(signals) > 0
        fr = None
        for s in signals:
            if fr:
                assert fr == s.frame_rate
            fr = s.frame_rate
        Signal.__init__(self, fr, False)
        self.signals = list(signals)
        self.num_signals = len(signals)
    def rewind(self):
        for sig in self.signals:
            sig.rewind()
    def add_signal(self, signal):
        self.signals.append(signal)
        self.num_signals += 1
    def _get_samples(self, left, right):
        sub_left  = numpy.zeros((len(left),),  dtype=numpy.int16)
        sub_right = numpy.zeros((len(right),), dtype=numpy.int16)
        has_more_data = False
        for sig in self.signals:
            has_more_data = sig._get_samples(sub_left, sub_right) or has_more_data
            for i in range(0, len(sub_left)):
                for e in sig._effects:
                    e.apply_to_samples(i, sub_left, sub_right, sig.frame_rate)
            left  += sub_left  #/ self.num_signals
            right += sub_right #/ self.num_signals
        return has_more_data



################################################################################
# EFFECTS
################################################################################

class Effect(object):
    def apply_to_samples(self, i, left, right, frame_rate):
        raise LibraryError('Effect subclass failed to override apply_to_samples')

class Amplifier(Effect):
    def __init__(self, gain):
        self.gain = gain
    def apply_to_samples(self, i, left, right, frame_rate):
        left[i]  *= self.gain
        right[i] *= self.gain

class Fader(Effect):
    def __init__(self, left_gain, right_gain):
        self.left_gain = left_gain
        self.right_gain = right_gain
    def apply_to_samples(self, i, left, right, frame_rate):
        left[i]  *= self.left_gain
        right[i] *= self.right_gain

class ComplexFader(Effect):
    def __init__(self, l_to_l, l_to_r, r_to_l, r_to_r):
        self.l_to_l = l_to_l
        self.l_to_r = l_to_r
        self.r_to_l = r_to_l
        self.r_to_r = r_to_r
    def apply_to_samples(self, i, left, right, frame_rate):
        l = left[i]
        r = right[i]
        left[i]   = l * self.l_to_l + r * self.r_to_l
        right[i]  = l * self.l_to_r + r * self.r_to_r

class Overdriver(Effect):
    def __init__(self, gain, cutoff):
        assert cutoff > 0
        self.gain = gain
        self.cutoff = cutoff
    def apply_to_samples(self, i, left, right, frame_rate):
        l = float(left[i])
        left[i]  = numpy.sign(l) * min(self.cutoff, abs(l * self.gain))
        r = float(right[i])
        right[i] = numpy.sign(r) * min(self.cutoff, abs(r * self.gain))

class Oscillator(Effect):
    def __init__(self, freq, amplitude):
        assert freq > 0
        self.freq = freq
        self.amplitude = amplitude
        self._ix_frame = 0
    def apply_to_samples(self, i, left, right, frame_rate):
        frames_per_cycle = frame_rate / self.freq
        d = self._ix_frame / float(frames_per_cycle)
        a = self.amplitude ** math.sin(2 * math.pi * d)
        left[i] *= a
        right[i] *= a
        self._ix_frame += 1
        if self._ix_frame >= frames_per_cycle:
            self._ix_frame = 0

class Compressor(Effect):
    def __init__(self, low_thresh, low_factor, high_thresh, high_factor):
        assert low_thresh <= high_thresh
        self.low_thresh = low_thresh
        self.low_factor = float(low_factor)
        self.high_thresh = high_thresh
        self.high_factor = float(high_factor)
    def apply_to_samples(self, i, left, right, frame_rate):
        l = float(abs(left[i]))
        if l < self.low_thresh:
            l = self.low_thresh - (self.low_thresh - l) / self.low_factor
        elif l > self.high_thresh:
            l = self.high_thresh + (l - self.high_thresh) / self.high_factor
        left[i]   = numpy.sign(left[i]) * l
        r = float(abs(right[i]))
        if r < self.low_thresh:
            r = self.low_thresh - (self.low_thresh - r) / self.low_factor
        elif r > self.high_thresh:
            r = self.high_thresh + (r - self.high_thresh) / self.high_factor
        right[i]  = numpy.sign(right[i]) * r
