import taichi as ti
import argparse
import os
import math
import numpy as np
import matplotlib.pyplot as plt
from custom.dynamicGen import linkGraph
import copy
import datetime
import pickle

real = ti.f32
ti.init(default_fp=real, arch=ti.gpu, flatten_if=True)

dim = 2
n_particles = 8192
n_solid_particles = 0
n_actuators = 0
n_grid = 128
dx = 1 / n_grid
inv_dx = 1 / dx
dt = 1e-3
p_vol = 1
E = 10
# TODO: update
mu = E
la = E
max_steps = 2048
steps = 1024
gravity = 3.8
target = [0.8, 0.2]

scalar = lambda: ti.field(dtype=real)
vec = lambda: ti.Vector.field(dim, dtype=real)
mat = lambda: ti.Matrix.field(dim, dim, dtype=real)

actuator_id = ti.field(ti.i32)
particle_type = ti.field(ti.i32)
x, v = vec(), vec()
grid_v_in, grid_m_in = vec(), scalar()
grid_v_out = vec()
C, F = mat(), mat()

loss = scalar()
xmin = scalar()


# higher base act strength and number of sin waves to get more dramatic movement faster.
n_sin_waves = 8
weights = scalar()
bias = scalar()
x_avg = vec()

actuation = scalar()
actuation_omega = 20
act_strength = 6


def allocate_fields():
    ti.root.dense(ti.ij, (n_actuators, n_sin_waves)).place(weights)
    ti.root.dense(ti.i, n_actuators).place(bias)

    ti.root.dense(ti.ij, (max_steps, n_actuators)).place(actuation)
    ti.root.dense(ti.i, n_particles).place(actuator_id, particle_type)
    ti.root.dense(ti.k, max_steps).dense(ti.l, n_particles).place(x, v, C, F)
    ti.root.dense(ti.ij, n_grid).place(grid_v_in, grid_m_in, grid_v_out)
    ti.root.place(loss, x_avg, xmin)

    ti.root.lazy_grad()


@ti.kernel
def clear_grid():
    for i, j in grid_m_in:
        grid_v_in[i, j] = [0, 0]
        grid_m_in[i, j] = 0
        grid_v_in.grad[i, j] = [0, 0]
        grid_m_in.grad[i, j] = 0
        grid_v_out.grad[i, j] = [0, 0]


@ti.kernel
def clear_particle_grad():
    # for all time steps and all particles
    for f, i in x:
        x.grad[f, i] = [0, 0]
        v.grad[f, i] = [0, 0]
        C.grad[f, i] = [[0, 0], [0, 0]]
        F.grad[f, i] = [[0, 0], [0, 0]]


@ti.kernel
def clear_actuation_grad():
    for t, i in actuation:
        actuation[t, i] = 0.0


@ti.kernel
def p2g(f: ti.i32):
    for p in range(n_particles):
        base = ti.cast(x[f, p] * inv_dx - 0.5, ti.i32)
        fx = x[f, p] * inv_dx - ti.cast(base, ti.i32)
        w = [
            0.5 * (1.5 - fx) ** 2,
            0.75 - (fx - 1) ** 2,
            0.5 * (fx - 0.5) ** 2,
        ]
        new_F = (ti.Matrix.diag(dim=2, val=1) + dt * C[f, p]) @ F[f, p]
        J = (new_F).determinant()
        if particle_type[p] == 0:  # fluid
            sqrtJ = ti.sqrt(J)
            new_F = ti.Matrix([[sqrtJ, 0], [0, sqrtJ]])

        F[f + 1, p] = new_F
        r, s = ti.polar_decompose(new_F)

        act_id = actuator_id[p]

        act = actuation[f, ti.max(0, act_id)] * act_strength
        if act_id == -1:
            act = 0.0
        # ti.print(act)

        A = ti.Matrix([[0.0, 0.0], [0.0, 1.0]]) * act
        cauchy = ti.Matrix([[0.0, 0.0], [0.0, 0.0]])
        mass = 0.0
        if particle_type[p] == 0:
            mass = 4
            cauchy = ti.Matrix([[1.0, 0.0], [0.0, 0.1]]) * (J - 1) * E
        else:
            mass = 1
            cauchy = 2 * mu * (new_F - r) @ new_F.transpose() + ti.Matrix.diag(2, la * (J - 1) * J)
        cauchy += new_F @ A @ new_F.transpose()
        stress = -(dt * p_vol * 4 * inv_dx * inv_dx) * cauchy
        affine = stress + mass * C[f, p]
        for i in ti.static(range(3)):
            for j in ti.static(range(3)):
                offset = ti.Vector([i, j])
                dpos = (ti.cast(ti.Vector([i, j]), real) - fx) * dx
                weight = w[i][0] * w[j][1]
                grid_v_in[base + offset] += weight * (mass * v[f, p] + affine @ dpos)
                grid_m_in[base + offset] += weight * mass


bound = 3
coeff = 0.5


@ti.kernel
def grid_op():
    for i, j in grid_m_in:
        inv_m = 1 / (grid_m_in[i, j] + 1e-10)
        v_out = inv_m * grid_v_in[i, j]
        v_out[1] -= dt * gravity
        if i < bound and v_out[0] < 0:
            v_out[0] = 0
            v_out[1] = 0
        if i > n_grid - bound and v_out[0] > 0:
            v_out[0] = 0
            v_out[1] = 0
        if j < bound and v_out[1] < 0:
            v_out[0] = 0
            v_out[1] = 0
            normal = ti.Vector([0.0, 1.0])
            lsq = (normal**2).sum()
            if lsq > 0.5:
                if ti.static(coeff < 0):
                    v_out[0] = 0
                    v_out[1] = 0
                else:
                    lin = v_out.dot(normal)
                    if lin < 0:
                        vit = v_out - lin * normal
                        lit = vit.norm() + 1e-10
                        if lit + coeff * lin <= 0:
                            v_out[0] = 0
                            v_out[1] = 0
                        else:
                            v_out = (1 + coeff * lin / lit) * vit
        if j > n_grid - bound and v_out[1] > 0:
            v_out[0] = 0
            v_out[1] = 0

        grid_v_out[i, j] = v_out


@ti.kernel
def g2p(f: ti.i32):
    for p in range(n_particles):
        base = ti.cast(x[f, p] * inv_dx - 0.5, ti.i32)
        fx = x[f, p] * inv_dx - ti.cast(base, real)
        w = [
            0.5 * (1.5 - fx) ** 2,
            0.75 - (fx - 1.0) ** 2,
            0.5 * (fx - 0.5) ** 2,
        ]
        new_v = ti.Vector([0.0, 0.0])
        new_C = ti.Matrix([[0.0, 0.0], [0.0, 0.0]])

        for i in ti.static(range(3)):
            for j in ti.static(range(3)):
                dpos = ti.cast(ti.Vector([i, j]), real) - fx
                g_v = grid_v_out[base[0] + i, base[1] + j]
                weight = w[i][0] * w[j][1]
                new_v += weight * g_v
                new_C += 4 * weight * g_v.outer_product(dpos) * inv_dx

        v[f + 1, p] = new_v
        x[f + 1, p] = x[f, p] + dt * v[f + 1, p]
        C[f + 1, p] = new_C


@ti.kernel
def compute_actuation(t: ti.i32):
    for i in range(n_actuators):
        act = 0.0
        for j in ti.static(range(n_sin_waves)):
            act += weights[i, j] * ti.sin(actuation_omega * t * dt + 2 * math.pi / n_sin_waves * j)
        act += bias[i]
        actuation[t, i] = ti.tanh(act)


@ti.kernel
def compute_x_avg():
    for i in range(n_particles):
        contrib = 0.0
        if particle_type[i] == 1:
            contrib = 1.0 / n_solid_particles
        ti.atomic_add(x_avg[None], contrib * x[steps - 1, i])


@ti.kernel
def compute_loss():
    dist = x_avg[None][0]
    loss[None] = -dist


@ti.ad.grad_replaced
def advance(s):
    clear_grid()
    compute_actuation(s)
    p2g(s)
    grid_op()
    g2p(s)


@ti.ad.grad_for(advance)
def advance_grad(s):
    clear_grid()
    p2g(s)
    grid_op()

    g2p.grad(s)
    grid_op.grad()
    p2g.grad(s)
    compute_actuation.grad(s)


def forward(total_steps=steps):
    # simulation
    for s in range(total_steps - 1):
        advance(s)
    x_avg[None] = [0, 0]
    compute_x_avg()
    compute_loss()


class Scene:
    def __init__(self):
        self.n_particles = 0
        self.n_solid_particles = 0
        self.x = []
        self.actuator_id = []
        self.particle_type = []
        self.offset_x = 0
        self.offset_y = 0

    def add_rect(self, x, y, w, h, actuation, ptype=1):
        if ptype == 0:
            assert actuation == -1
        global n_particles
        w_count = int(w / dx) * 2
        h_count = int(h / dx) * 2
        real_dx = w / w_count
        real_dy = h / h_count
        for i in range(w_count):
            for j in range(h_count):
                self.x.append(
                    [
                        x + (i + 0.5) * real_dx + self.offset_x,
                        y + (j + 0.5) * real_dy + self.offset_y,
                    ]
                )
                self.actuator_id.append(actuation)
                self.particle_type.append(ptype)
                self.n_particles += 1
                self.n_solid_particles += int(ptype == 1)

    def set_offset(self, x, y):
        self.offset_x = x
        self.offset_y = y

    def finalize(self):
        global n_particles, n_solid_particles
        n_particles = self.n_particles
        n_solid_particles = self.n_solid_particles
        print('n_particles', n_particles)
        print('n_solid', n_solid_particles)

    def set_n_actuators(self, n_act):
        global n_actuators
        n_actuators = n_act


gui = ti.GUI("Differentiable MPM", (640, 640), background_color=0x000000)


def visualize(s, folder):
    aid = actuator_id.to_numpy()
    colors = np.empty(shape=n_particles, dtype=np.uint32)
    particles = x.to_numpy()[s]
    actuation_ = actuation.to_numpy()
    for i in range(n_particles):
        color = 0xFFFFFF
        if aid[i] != -1:
            act = actuation_[s - 1, int(aid[i])]
            color = ti.rgb_to_hex((0.5 - act, 0.5 - abs(act), 0.5 + act))
        colors[i] = color
    gui.circles(pos=particles, color=colors, radius=1.5)
    gui.line((0.05, 0.02), (0.95, 0.02), radius=3, color=0xFFFFFF)

    os.makedirs(folder, exist_ok=True)
    gui.show(f'{folder}/{s:04d}.png')


def train(robot, iters):
    scene = Scene()
    robot.generateRobot(scene)
    scene.finalize()

    for i in range(n_actuators):
        # Reset bias, this is a manual change
        bias[i] = 0.0
        for j in range(n_sin_waves):
            weights[i, j] = np.random.randn() * 0.01

    for i in range(scene.n_particles):
        x[0, i] = scene.x[i]
        F[0, i] = [[1, 0], [0, 1]]
        actuator_id[i] = scene.actuator_id[i]
        particle_type[i] = scene.particle_type[i]

    losses = []
    for iter in range(iters):
        with ti.ad.Tape(loss):
            forward()
        l = loss[None]
        losses.append(l)
        if iter % 10 == 0:
            print('i=', iter, 'loss=', l)
        learning_rate = 0.1

        for i in range(n_actuators):
            for j in range(n_sin_waves):
                weights[i, j] -= learning_rate * weights.grad[i, j]
            bias[i] -= learning_rate * bias.grad[i]

        robot.loss = l

        if iter == iters - 1:
            forward(2000)
            for s in range(15, 2000, 16):
                visualize(s, 'diffmpm/iter{:03d}/'.format(iter))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iters', type=int, default=50)
    options = parser.parse_args()

    # initialization
    # bottom, top, left, right (does not have to equal 1.0)
    blockweights = [0.50, 0.50, 0.50, 0.50]
    popSize = 1
    robotSize = 16
    blockSize = 0.035

    genNum = 0

    gens = []

    # build one parent just to call allocate_fields
    parent = linkGraph(blockSize, blockweights)
    parent.buildToTarget(robotSize)
    scene = Scene()
    parent.generateRobot(scene)
    scene.finalize()
    allocate_fields()

    # build initial set
    children = []

    # This toggles allows resuming the evolution from a generation saved to a file
    if False:
        for i in range(popSize):
            file = f'creatureDumps/2025-03-13_14-20-04/gen2child{i}parent1,8'
            with open(file, 'rb') as f:
                child = pickle.load(f)
                child.num = i
                children.append(child)
    else:
        for i in range(popSize):
            member = linkGraph(blockSize, blockweights)
            member.buildToTarget(robotSize)
            member.num = i
            children.append(member)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    os.mkdir(f'creatureDumps/{timestamp}')

    for i, child in enumerate(children):
        file = f'creatureDumps/{timestamp}/gen{genNum}child{i}'
        with open(file, 'wb') as f:
            pickle.dump(child, f)

    for i, child in enumerate(children):
        print("Child ", i + 1)
        train(child, options.iters)
        print("Best loss: ", child.loss)

    # pick best of initial population
    bestloss = 0.0
    bestChild = None
    for child in children:
        if child.loss < bestloss:
            bestChild = child
            bestloss = child.loss

    parent = bestChild
    # make children and evolve
    for a in range(100):
        print("Gen: ", a + 1)
        for i in range(popSize):
            child = copy.deepcopy(parent)
            child.remove(5)
            child.buildToTarget(robotSize)
            child.gen = a + 1
            child.num = i
            children[i] = child

        # Train all children and record last loss
        for i, child in enumerate(children):
            print("Child ", i)
            train(child, options.iters)

        # pick best of children
        bestloss = 0.0
        bestChild = None
        for i, child in enumerate(children):
            if child.loss < bestloss:
                bestChild = child
                bestloss = child.loss

        print("Best loss from previous training: ", bestloss)
        gens.append(bestloss)
        genNum += 1

        # Write to file
        for i, child in enumerate(children):
            file = f'creatureDumps/{timestamp}/gen{genNum}child{i}parent{parent.gen},{parent.num}'
            with open(file, 'wb') as f:
                pickle.dump(child, f)
        if bestChild.loss < parent.loss:
            parent = bestChild

        else:
            print("Not better than parent!")


if __name__ == '__main__':
    main()
