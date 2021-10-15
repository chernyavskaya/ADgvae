import sys
import torch
import torch.nn.functional as F
import scipy.optimize
import numpy as np
import os.path as osp
import torch.nn.functional as F
from torch_geometric.data import Data
from torch_geometric.utils import to_dense_batch

multi_gpu = torch.cuda.device_count()>1
eps = 1e-12
torch.autograd.set_detect_anomaly(True)


def xyze_to_ptetaphi_torch(y):
    ''' converts an array [N x 100, 4] of particles
from px, py, pz, E to pt,eta, phi
    '''
    PX_idx, PY_idx, PZ_idx, E_idx = range(4)
    pt = torch.sqrt(torch.pow(y[:,PX_idx], 2) + torch.pow(y[:,PY_idx], 2)) 
    eta = torch.asinh(torch.where(pt < 10e-5, torch.zeros_like(pt), torch.div(y[:,PZ_idx], pt)))
    phi = torch.atan2(y[:,PY_idx], y[:,PX_idx])

    #relu =  m = nn.ReLU() #inplace=True  #This is actually not needed for E if min-max normalization is used for pt,E, AND!! relu is used as an activation function.
   # y_E_trimmed = relu(y[:,E_idx]) #trimming E
    #y_pt_trimmed = relu(pt) #trimming pt
   # full_y = torch.stack((y[:,PX_idx],y[:,PY_idx],y[:,PZ_idx],y_E_trimmed,y_pt_trimmed,eta,phi), dim=1)
   # full_y = torch.stack((y[:,PX_idx],y[:,PY_idx],y[:,PZ_idx],y[:,E_idx],y_pt_trimmed,eta,phi), dim=1)
    full_y = torch.stack((y[:,PX_idx],y[:,PY_idx],y[:,PZ_idx],y[:,E_idx],pt,eta,phi), dim=1)

    return full_y


class LossFunction:
    def __init__(self, lossname, beta = 0.5,device=torch.device('cuda:0')):
        loss = getattr(self, lossname)
        self.name = lossname
        self.loss_ftn = loss
        self.device = device
        self.beta = beta
        
    def mse(self, x, y):
        return F.mse_loss(x, y, reduction='mean')
    
    def mse_coordinates(self, y,x): #for some reason convension is : out,in
        #From px,py,pz,E get pt, eta, phi (do not predict them)
        #x is px,py,pz,E,pt,eta,phi
        #y is px,py,pz,E
        full_y = xyze_to_ptetaphi_torch(y)
        return self.mse(x,full_y)

    # Reconstruction + KL divergence losses
    def vae_loss_mse_coord(self, x, y, mu, logvar):
        MSE = self.mse_coordinates(y,x)
        # 0.5 * sum(1 + log(sigma^2) - mu^2 - sigma^2)
        KLD = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
        return (1-self.beta)*MSE + self.beta*KLD, MSE, KLD
        
    # Reconstruction + KL divergence losses
    def vae_loss_mse(self, x, y, mu, logvar):
        MSE = self.mse(y,x)
        # 0.5 * sum(1 + log(sigma^2) - mu^2 - sigma^2)
        KLD = -0.5 * torch.sum(1 + logvar - mu.pow(2) - logvar.exp())
        return (1-self.beta)*MSE + self.beta*KLD, MSE, KLD

