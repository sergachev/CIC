from fixedpoint import FixedPoint
from bitstring import BitArray

import math
import numpy as np

class Model:
    def __init__(self, R, M, N , INP_DW, OUT_DW, register_pruning=1):
        self.R = R
        self.M = M
        self.N = N
        self.INP_DW = INP_DW
        self.OUT_DW = OUT_DW
        self.register_pruning = register_pruning

        self.cic_taps = np.zeros(R * M * N)
        self.cic_push_ptr = 0

        CIC_Filter_Gain = (self.R*self.M)**self.N        
        Num_of_Bits_Growth = np.ceil(math.log2(CIC_Filter_Gain))
        self.Num_Output_Bits_With_No_Truncation = Num_of_Bits_Growth + self.INP_DW - 1
        print(f"B_max: {self.Num_Output_Bits_With_No_Truncation}")
        if True:
            self.calculate_register_pruning()

    def calculate_register_pruning(self):
        # calculate register pruning as described in Hogenauer, 1981
        F_j = np.zeros(2*self.N + 2)
        for j in np.arange(2*self.N,0,-1):
            h_j = np.zeros((self.R*self.M-1)*self.N + 2*self.N)
            if j <= self.N:
                for k in np.arange((self.R*self.M-1)*self.N + j - 1):
                    for L in range(int(np.floor(k/(self.R*self.M))) + 1):
                        h_j[k] += (-1)**L*self.binom(self.N, L)*self.binom(self.N - j + k - self.R*self.M*L, k - self.R*self.M*L)
            else:
                for k in np.arange(2*self.N + 1 - j + 1):
                    h_j[k] = (-1)**k*self.binom(2*self.N + 1 - j, k)

            F_j[j] = np.sqrt(np.dot(h_j,h_j))

        F_j[2*self.N + 1]=1

        Num_of_Output_Bits_Truncated = self.Num_Output_Bits_With_No_Truncation - self.OUT_DW + 1
        sigma = np.sqrt((2**Num_of_Output_Bits_Truncated)**2/12)

        self.B_j = np.floor(-np.log2(F_j) + np.log2(sigma) + 0.5*math.log2(6/self.N));        

        for j in np.arange(1, 2*self.N+1):
            print(f"F_{j} = {F_j[j]}  \t -log_2(F_j) = {-np.log2(F_j[j])} \t B_j = {self.B_j[j]} \t bits = {self.Num_Output_Bits_With_No_Truncation - self.B_j[j]}")
        print(f"F_{2*self.N+1} = {F_j[2*self.N+1]}  \t\t\t -log_2(F_j) = {-np.log2(F_j[2*self.N+1])} \t B_j = {Num_of_Output_Bits_Truncated} \t bits = {self.OUT_DW}")

    def cic_model_stage_get_out(self, stage):
        ret = 0
        for i_t in np.arange(self.R*self.M):
            ret += self.cic_taps[i_t + stage * self.R*self.M]
        return ret

    def push_data(self, data_in):
        for i_s in np.arange(self.N-1,0,-1):
            self.cic_taps[self.cic_push_ptr + i_s * self.R*self.M] = self.cic_model_stage_get_out(i_s - 1)
        self.cic_taps[self.cic_push_ptr] = data_in
        self.cic_push_ptr = self.cic_push_ptr + 1 if self.cic_push_ptr < self.R*self.M - 1 else 0

    def get_data(self):
        cic_B_scale_out = self.Num_Output_Bits_With_No_Truncation + 1 - self.OUT_DW
        cic_B_prune_last_stage = cic_B_scale_out
        cic_S_prune_last_stage = int(1) << int(cic_B_prune_last_stage)
        return self.cic_model_stage_get_out(self.N - 1) // cic_S_prune_last_stage

    def binom(self, n, k):
        return math.factorial(n) // math.factorial(k) // math.factorial(n - k)
    