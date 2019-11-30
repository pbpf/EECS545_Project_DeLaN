'''

    Generates character reference trajectories in [q, q_dot, q_ddot]

'''
import numpy as np
from scipy.io import loadmat
import copy

def J(q, l1=0.5, l2=0.5):
    ''' gets jacobian fcn - l1 and l2 are link lengths '''
    return np.asarray([[-l1 * np.sin(q[0]) - l2 * np.sin(q[0] + q[1]), -l2 * np.sin(q[0] + q[1])],
                     [l1 * np.cos(q[0]) + l2 * np.cos(q[0] + q[1]), l2 * np.cos(q[0] + q[1])]])

def M(q, l1=0.5, l2=0.5, m1 = 0.5, m2 = 0.5):
    ''' calculates mass matrix where (l1, l2) are link lengths and (m1, m2) are link masses '''
    return np.array([[m1 * l1**2 + m2 * (l1**2 + 2 * l1 * l2 * np.cos(q[1]) + l2**2), m2 * (l1 * l2 * np.cos(q[1]) + l2**2)],
                    [m2 * (l1 * l2 * np.cos(q[1]) + l2**2), m2 * l2**2]])

def c(q, q_dot, l1=0.5, l2=0.5, m1 = 0.5, m2 = 0.5):
    ''' calculates Coriolis and centripetal torques where (l1, l2) are link lengths and (m1, m2) are link masses '''
    return np.array([[-m2 * l1 * l2 * np.sin(q[1]) * (2 * q_dot[0] * q_dot[1] + q_dot[1]**2)],
                    [m2 * l1 * l2 * (q_dot[0]**2) * np.sin(q[1])]])

def g(q, l1=0.5, l2=0.5, m1 = 0.5, m2 = 0.5):
    ''' calculates gravitational torque where (l1, l2) are link lengths and (m1, m2) are link masses '''
    g = 0.0
    return np.array([[(m1 + m2) * l1 * g * np.cos(q[0]) + m2 * g * l2 * np.cos(q[0] + q[1])],
                    [m2 * g * l2 * np.cos(q[0] + q[1])]])

def torque(q_ddot, M, c, g):
    ''' calculates torque, given acceleration (q_ddot), mass matrix (M), Coriolis and centripetal torques (c) and gravitational torques (g)'''
    return M @ q_ddot + c + g

def load_data():
    data = loadmat('../data/mixoutALL_shifted.mat')

    # Char labels N x 1 vec of labels 1-20
    char_labels = data['consts']['charlabels'][0][0].T

    # Key maps label to character via key[label-1]
    key = data['consts']['key'][0][0].T.squeeze()

    # Trajectories in list of N trajectories - each may be a different length so cannot put into one matrix
    trajectories = data['mixout'].T

    return trajectories, char_labels, key


def convert_trajectory(trajectory, sample_rate=200):
    '''
        converts trajectory from end effector v to q_dot
        -- right now assuming that we start at same position every time -- can change
    '''
    q_init = np.asarray([np.pi / 4.0, np.pi / 2.0])
    q = q_init.copy()
    q_dot = []
    for i in range(len(trajectory)):
        # q_dot
        v = trajectory[i, :2]
        q_d = np.linalg.solve(J(q), v)
        q += q_d / sample_rate
        q_dot.append(q_d)

    q_dot = np.asarray(q_dot)
    q = q_init + np.cumsum(q_dot, axis=0) / sample_rate
    q_ddot = np.concatenate((np.zeros((1, 2)), np.diff(q_dot, axis=0))) * sample_rate

    return np.concatenate((q, q_dot, q_ddot), axis=1)

def trajectory_torque(trajectory_joint_space):
    '''
        calculates M, c, g and tau given a trajectory of joint angles, velocities and accelerations
    '''
    q = trajectory_joint_space[:,:2]
    q_dot = trajectory_joint_space[:,2:4]
    q_ddot = trajectory_joint_space[:,4:]

    n, d = q.shape

    M_list = np.zeros((n,d,d))
    c_list = np.zeros((n,d))
    g_list = np.zeros((n,d))
    tau_list = np.zeros((n,d))

    for i in range(n):

        M_i = M(q[i,:])
        # L_i = np.linalg.cholesky(M_i)
        # if L_i[1,0] < 0:
        #     print("Negative")
        c_i = c(q[i,:], q_dot[i,:])
        g_i = g(q[i,:])
        tau_i = torque(q_ddot[[i],:].T, M_i, c_i, g_i)

        M_list[i,:,:] = M_i
        c_list[i,:] = c_i.reshape((1,d))
        g_list[i,:] = g_i.reshape((1,d))
        tau_list[i,:] = tau_i.reshape((1,d))

    return (M_list, c_list, g_list, tau_list)

if __name__ =='__main__':

    trajectories, labels, key = load_data()
    joint_trajectories = []
    M_list = []
    c_list = []
    g_list = []
    tau_list = []

    joint_trajectories_concat = None
    tau_list_concat = None

    # It takes a minutes or two so wanted to print out status
    for i, trajectory in enumerate(trajectories.flatten()):
        print("Converting trajectory #", str(i))
        trajectory_joint_space = convert_trajectory(trajectory.T)
        trajectory_M, trajectory_c, trajectory_g, trajectory_tau = trajectory_torque(trajectory_joint_space)

        # create concatenated dataset for neural network training
        # if i == 0:
        #     joint_trajectories_concat = trajectory_joint_space
        #     tau_list_concat = trajectory_tau
        # else:
        #     joint_trajectories_concat = np.vstack((joint_trajectories_concat,trajectory_joint_space))
        #     tau_list_concat = np.vstack((tau_list_concat,trajectory_tau))

        joint_trajectories.append(trajectory_joint_space)
        M_list.append(trajectory_M)
        c_list.append(trajectory_c)
        g_list.append(trajectory_g)
        tau_list.append(trajectory_tau)

    # joint_data = dict()
    # joint_data['M'] = M_list
    # joint_data['c'] = c_list
    # joint_data['g'] = g_list
    # joint_data['torques'] = tau_list
    # joint_data['trajectories'] = joint_trajectories
    # joint_data['char_label'] = labels
    # joint_data['char_keys'] = key

    np.savez('../data/trajectories_joint_space_no_gravity.npz', trajectories = joint_trajectories,
                                                    labels = labels,
                                                    keys = key,
                                                    torques = tau_list,
                                                    H = M_list,
                                                    c = c_list,
                                                    g = g_list
                                                    )
    # np.savez('../data/trajectories_train_joint_space.npz', trajectories = joint_trajectories_concat,
    #                                                 torques = tau_list_concat
    #                                                 )

