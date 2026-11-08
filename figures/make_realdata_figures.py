import json, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
D=json.load(open('/tmp/w/final/denominator.json'))
R=json.load(open('/mnt/user-data/outputs/results/results.json'))
c=np.load('/tmp/w/final/curves.npz')
TEAL,AMBER,GRAY,INK='#0f766e','#b45309','#6b7785','#1f2937'
plt.rcParams.update({'font.size':8,'axes.spines.top':False,'axes.spines.right':False,
 'axes.edgecolor':'#9ca3af','xtick.color':GRAY,'ytick.color':GRAY,'axes.labelcolor':INK,'axes.titlecolor':INK})
P=R['primary']; I=R['ip16']; S=D['replica_structure']
# real graph: convert per-fleet -> per-component
k=P['N']/P['giant_n']
fs_c=c['fs']*k; tgt_c=c['tgt']/P['giant_frac']
qs_c=c['qs']*k; rnd_c=c['rnd']/P['giant_frac']
real_theory_c=P['hub_theory']*k

# ---------- Figure 2: coverage, per component ----------
cr=np.load('/tmp/w/final/creation.npz')
fig,ax=plt.subplots(1,3,figsize=(9.6,2.9))
ax[0].plot(qs_c,rnd_c,color=TEAL,lw=2,label='real swarm')
ax[0].axvline(P['random_theory'],color=TEAL,ls=':',lw=1)
ax[0].text(P['random_theory']-.03,.55,'theory %.2f'%P['random_theory'],rotation=90,fontsize=6.5,color=TEAL,ha='right',va='center')
ax[0].axvline(S['rand_half'],color=AMBER,ls='--',lw=1)
ax[0].text(S['rand_half']+.03,.80,'replica\nhalf-point',fontsize=6.3,color=AMBER)
ax[0].set_title('Random loss',fontsize=8.5,loc='left')
ax[0].set_xlabel('share of the coupled component unobserved'); ax[0].set_ylabel('largest component (share of initial)')
ax[0].set_xlim(0,1.0)
ax[1].plot(fs_c,tgt_c,color=TEAL,lw=2)
ax[1].axvline(real_theory_c,color=TEAL,ls=':',lw=1)
ax[1].text(real_theory_c-.012,.55,'theory %.2f'%real_theory_c,rotation=90,fontsize=6.5,color=TEAL,ha='right',va='center')
ax[1].axvline(S['theory_perComp'],color=AMBER,ls='--',lw=1)
ax[1].text(S['theory_perComp']+.012,.72,'replica theory\n%.2f'%S['theory_perComp'],fontsize=6.3,color=AMBER)
ax[1].set_title('Highest-degree nodes blinded first',fontsize=8.5,loc='left')
ax[1].set_xlabel('share of the coupled component blinded'); ax[1].set_xlim(0,0.45)
ax[2].plot(cr['keeps'],cr['curve']/P['giant_frac'],color=TEAL,lw=2)
ax[2].axhline(0.5,color=GRAY,ls=':',lw=.9)
ax[2].text(0.55,0.53,'half of initial size',fontsize=6.5,color=GRAY)
ax[2].set_title('Creation events lost',fontsize=8.5,loc='left')
ax[2].set_xlabel('share of creation records retained')
for a in ax: a.set_ylim(0,1.05)
plt.tight_layout(); plt.savefig('/mnt/user-data/outputs/figures/fig_real_coverage.png',dpi=200)
print('fig2 done | real hub theory per-component %.3f | replica %.3f'%(real_theory_c,S['theory_perComp']))

# ---------- Figure 3: denominator, identity, timing ----------
fig,ax=plt.subplots(1,3,figsize=(9.6,2.95))
sw=D['prevalence_sweep']; pv=[100*s['prevalence'] for s in sw]
ax[0].plot(pv,[s['theory_perN'] for s in sw],color=AMBER,lw=2,marker='o',ms=4,label='as a share of the fleet')
ax[0].plot(pv,[s['theory_perComp'] for s in sw],color=TEAL,lw=2,marker='s',ms=4,label='as a share of the component')
ax[0].set_xlabel('swarm prevalence in the fleet (%)'); ax[0].set_ylabel('predicted hub-collapse threshold')
ax[0].set_ylim(0,0.5); ax[0].legend(fontsize=6.6,frameon=False,loc='center left')
ax[0].set_title('Only one of these transfers',fontsize=8.5,loc='left')
ax[0].text(13,0.46,'%.1fx spread'%D['prevalence_spread']['perComp_ratio'],fontsize=6.5,color=TEAL)
ax[0].text(13,0.02,'%.1fx spread'%D['prevalence_spread']['perN_ratio'],fontsize=6.5,color=AMBER)
ax[1].plot(fs_c,tgt_c,color=TEAL,lw=2,label='agent-chosen names (R=%.0f)'%P['R'])
ax[1].plot(c['fs2']*I['N']/I['giant_n'],c['tgt2']/I['giant_frac'],color=AMBER,lw=2,label='network /16 prefix (R=%.0f)'%I['R'])
ax[1].axvline(real_theory_c,color=TEAL,ls=':',lw=1); ax[1].axvline(I['hub_theory'],color=AMBER,ls=':',lw=1)
ax[1].set_xlim(0,0.65); ax[1].set_ylim(0,1.05)
ax[1].set_xlabel('share of component blinded'); ax[1].set_ylabel('largest component (share of initial)')
ax[1].legend(fontsize=6.3,frameon=False,loc='upper right')
ax[1].set_title('Identity layer moves it again',fontsize=8.5,loc='left')
sizes=[4,8,16,32,64,128,256,500]
real=[R['growth_real_days'][str(s)] for s in sizes]; nul=R['growth_null_days']
ax[2].fill_between(sizes,[nul[str(s)]['lo'] for s in sizes],[nul[str(s)]['hi'] for s in sizes],color=GRAY,alpha=.22,label='shuffled labels (95%)')
ax[2].plot(sizes,[nul[str(s)]['median'] for s in sizes],color=GRAY,lw=1.5,ls='--',label='shuffled (median)')
ax[2].plot(sizes,real,color=TEAL,lw=2,marker='o',ms=3.2,label='real swarm')
ax[2].set_xscale('log',base=2); ax[2].set_xticks(sizes); ax[2].set_xticklabels([str(s) for s in sizes],fontsize=6.5)
ax[2].set_xlabel('component size reached'); ax[2].set_ylabel('days after first coupling')
ax[2].legend(fontsize=6.3,frameon=False,loc='upper left')
ax[2].set_title('Growth timing carries no signal',fontsize=8.5,loc='left')
plt.tight_layout(); plt.savefig('/mnt/user-data/outputs/figures/fig_real_identity_timing.png',dpi=200)
print('fig3 done')
