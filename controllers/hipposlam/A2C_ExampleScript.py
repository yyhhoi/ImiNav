# Paths
from os.path import join

import gymnasium as gym
import numpy as np
import torch
import matplotlib.pyplot as plt

from hipposlam.Replay import ReplayMemoryA2C
from hipposlam.Networks import ActorModel, ValueCriticModel
from hipposlam.ReinforcementLearning import compute_discounted_returns, A2C

# Paths and parameters
env = gym.make("CartPole-v1")
obs_dim = 4
act_dim = 2
gamma = 0.99
batch_size = 256
max_buffer_size = 512
critic_lr = 1e-3
actor_lr = 1e-3
weight_decay = 1e-5
Niters = 500



# Networks
critic = ValueCriticModel(obs_dim)
actor = ActorModel(obs_dim, act_dim, logit=True)

# Replay Memory
memory = ReplayMemoryA2C(max_size=max_buffer_size)
datainds = np.cumsum([obs_dim, 1, 1])
memory.specify_data_tuple(s=(0 , datainds[0]),
                          a=(datainds[0], datainds[1]),
                          G=(datainds[1], datainds[2]))


# AWAC wrapper
agent = A2C(critic=critic,
            actor=actor,
            gamma=gamma,
            critic_lr=critic_lr,
            actor_lr=actor_lr,
            weight_decay=weight_decay)
rewards_alleps = []
critic_losses, actor_losses = [], []
maxtimesteps = 300
for n_epi in range(Niters):
    print('\rEpisode %d/%d'%(n_epi, Niters), flush=True, end='')
    s, _ = env.reset()
    cum_r = 0
    truncated = False
    candidates = []
    r_all, end_all = [], []
    t = 0
    while True and (truncated is False) and (t < maxtimesteps):
        s = torch.from_numpy(s).to(torch.float32).view(-1, obs_dim)  # (1, obs_dim)
        a = int(agent.get_action(s).squeeze())  # tensor (1, 1) -> int
        snext, r, done, truncated, info = env.step(a)
        r_all.append(r)
        end_all.append(done)

        experience = torch.concat([
            s.squeeze(), torch.tensor([a])
        ])
        candidates.append(experience)
        s = snext
        cum_r += 1
        t += 1
        if done:
            rewards_alleps.append(cum_r)
            break

    # Last v
    with torch.no_grad():
        s = torch.from_numpy(s).to(torch.float32).view(-1, obs_dim)
        last_v = critic(s)

    # Compute Returns
    traj = torch.vstack(candidates)
    G = compute_discounted_returns(r_all, end_all, last_v.squeeze().detach().item(), gamma)
    traj = torch.hstack([traj, torch.from_numpy(G).to(torch.float32).view(-1, 1)])


    _s = traj[:, :obs_dim]
    _a = traj[:, obs_dim:obs_dim+1].to(torch.int64)
    _G = traj[:, -1:]
    critic_loss, actor_loss = agent.update_networks(_s, _a, _G)
    critic_losses.append(critic_loss.item())
    actor_losses.append(actor_loss.item())

fig, ax = plt.subplots(1, 3, figsize=(10, 3))
ax[0].plot(rewards_alleps)
ax[0].set_ylabel('Cum R')
ax[1].plot(critic_losses)
ax[1].set_ylabel('Critic loss')
ax[2].plot(actor_losses)
ax[2].set_ylabel('Actor loss')
fig.savefig('A2C.png', dpi=200)
plt.show()
