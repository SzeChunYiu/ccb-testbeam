# Synthetic ROC/AP verification; paper claim NOT_AUTHORIZED.
import numpy as np
def legacy(y,s,w):
 y=np.asarray(y);s=np.asarray(s);w=np.asarray(w,float);o=np.argsort(-s);y,s,w=y[o],s[o],w[o]
 p=w[y==1].sum();n=w[y==0].sum()
 if not p or not n:return None
 tp=np.cumsum(w*y);fp=np.cumsum(w*(1-y));rec=tp/p;prec=tp/(tp+fp+1e-30)
 return float(np.trapezoid(np.r_[0,tp/p,1],np.r_[0,fp/n,1])),float(np.sum((rec[1:]-rec[:-1])*prec[1:]))
def correct(y,s,w):
 y=np.asarray(y);s=np.asarray(s);w=np.asarray(w,float);o=np.argsort(-s,kind='stable');y,s,w=y[o],s[o],w[o]
 p=w[y==1].sum();n=w[y==0].sum()
 if not p or not n:return None
 ends=np.r_[np.flatnonzero(np.diff(s)!=0),len(s)-1]
 tp=np.cumsum(w*y)[ends];fp=np.cumsum(w*(1-y))[ends];rec=tp/p
 return float(np.trapezoid(np.r_[0,rec],np.r_[0,fp/n])),float(np.sum(np.diff(np.r_[0,rec])*tp/(tp+fp)))
if __name__=='__main__':
 assert legacy([1,0],[.5,.5],[1,1])==(1.,0.)
 assert legacy([0,1],[.5,.5],[1,1])==(0.,.5)
 assert correct([1,0],[.5,.5],[1,1])==(.5,.5)
 assert correct([1,0],[.9,.1],[1,1])==(1.,1.)
 assert legacy([1,0],[.9,.1],[1,1])==(1.,0.)
 n=5093+330;eligible=max(1,n//500)*500
 assert n==5423 and eligible==5000 and n-eligible==423
 assert np.bincount((np.arange(n)//2000)%5,minlength=5).tolist()==[2000,2000,1423,0,0]
 print('SCOPED_PASS, NOT SCIENTIFIC RELEASE')
