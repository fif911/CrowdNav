# -*- coding: utf-8 -*-

class PID():
    """Software Implementation of a PID Controller"""

    def __init__(self, P=0, I=0, D=0, normalize=False):
        self.update(P, I, D)
        self.normalized = normalize

    def calculate(self, err, hist, derivative):
        return self.P * err + \
               self.I * sum(hist) / (len(hist) * 1.0 if self.normalized else 1.0) + \
               self.D * derivative

    def update(self, P, I, D):
        self.P = P
        self.I = I
        self.D = D


class ForgettingFactorPID(PID):
    def __init__(self, *args, **kwargs):
        if "Beta" in kwargs:
            self.Beta = kwargs["Beta"]
        else:
            self.Beta = 1
        super.__init__(self, args, kwargs)

    def calculate(self, err, hist, derivative):
        return self.P * err + \
               self.I * sum([h * self.Beta ** ix for ix, h in enumerate(reversed(hist))]) / (
                   len(hist) if self.normalized else 1) + \
               self.D * derivative
