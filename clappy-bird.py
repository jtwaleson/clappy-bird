#!/usr/bin/env python

from multiprocessing import Process, RawArray, Value
from time import sleep
from ConfigParser import SafeConfigParser
import time
import curses
import signal
import sys
import random


class StateProcess(Process):

    def __init__(self, config, target, args=(), name=None):
        self.config = config
        super(StateProcess, self).__init__(target=target, args=args, name=name)

    @property
    def state(self):
        return self.config.state.value

    @state.setter
    def state(self, value):
        self.config.state.value = value

    def log(self, string, log_file='/tmp/clappy.log'):
        with open(log_file, 'a') as f:
            f.write('%s (%s) %s \n' % (time.strftime("%H:%M:%S"), self.name,
                                       string))


class Screen(StateProcess):

    def __init__(self, config, data, clappy, fps=10):
        self.data = data
        self.clappy = clappy
        self.interval = 1.0/fps

        self.screen = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        begin_x = 10
        begin_y = 5
        self.height = config.height
        self.width = config.width
        self.win = curses.newwin(self.height, self.width, begin_y, begin_x)

        super(Screen, self).__init__(config, target=self.draw,
                                     args=(self.data, self.clappy,
                                           self.interval), name='Screen')

    @staticmethod
    def reset(self):
        curses.nocbreak()
        curses.echo()
        curses.curs_set(1)
        curses.endwin()

    def draw_clappy(self):
        c1 = "__(o>"
        if self.state == 3:
            c1 = "__(x>"
        c2 = "\__/"

        self.win.addstr(self.clappy.position - 1, self.width/2,
                        c1, curses.A_BOLD)
        self.win.addstr(self.clappy.position, self.width/2,
                        c2, curses.A_BOLD)

    def draw(self, data, clappy, interval):
        while (self.state != 4):
            self.win.erase()
            for i in range(0, self.height - 1):
                self.win.addstr(i, 0, data[i*100:i*100+self.width],
                                curses.A_BOLD)
            self.draw_clappy()
            self.win.refresh()
            sleep(interval)


class Controller(StateProcess):

    def __init__(self, config, screen, world):
        self.screen = screen
        self.world = world
        super(Controller, self).__init__(config, target=self.control,
                                         name='Controller')

    def control(self):
        while (self.state != 4):
            key = self.screen.screen.getch()
            if key == ord(' '):
                self.world.action()
            elif key == ord('q'):
                self.state = 4
                self.screen.reset(self.screen)


class World(StateProcess):

    def __init__(self, config, clappy):
        self.clappy = clappy
        self.height = config.height
        self.width = config.width + 20

        self.obstacle_width = 10
        self.obstacle_h_gap = 50
        self.obstacle_v_gap = config.obstacle_gap
        self.world = RawArray('c', self.height * self.width)
        self.init()

        super(World, self).__init__(config, target=self.evolve, name='World')

    def init(self):

        self.evolution = 0
        self.c = ' '
        self.gap = random.randint(1, self.height - self.obstacle_v_gap - 1)
        for i in range(0, len(self.world)):
            self.world[i] = ' '

    def action(self):
        if self.state == 1:
            self.state = 2
        elif self.state == 2:
            self.clappy.fly()
        elif self.state == 3:
            self.state = 1
            self.init()
        elif self.state == 4:
            pass

    def pos(self, i, j):
        return i * self.width + j

    def generate_gap(self):
        return random.randint(1, self.height - self.obstacle_v_gap - 1)

    def collision(self):
        p = self.pos
        cx = self.config.width/2
        cy = self.clappy.position

        if self.world[p(cy - 1, cx)] == '#' \
           or self.world[p(cy - 1, cx + 5)] == '#' \
           or self.world[p(cy, cx)] == '#' \
           or self.world[p(cy, cx + 5)] == '#':
            self.state = 3

    def evolve(self):
        p = self.pos
        W = self.world
        w = self.width

        while (self.state != 4):
            if self.state == 2:
                if self.evolution % self.obstacle_width == 0:
                    self.c = ' '
                if self.evolution % self.obstacle_h_gap == 0:
                    if self.c == ' ':
                        self.gap = self.generate_gap()
                        self.c = '#'
                    else:
                        self.c = ' '

                ceiling = range(0, self.gap)
                middle = range(self.gap, self.gap + self.obstacle_v_gap)
                floor = range(self.gap + self.obstacle_v_gap, self.height)

                for i in ceiling:
                    W[p(i, 0):p(i, w - 1)] = W[p(i, 1):p(i, w - 1)] + self.c

                for i in middle:
                    W[p(i, 0):p(i, w - 1)] = W[p(i, 1):p(i, w - 1)] + ' '

                for i in floor:
                    W[p(i, 0):p(i, w - 1)] = W[p(i, 1):p(i, w - 1)] + self.c

                self.collision()

                self.evolution = self.evolution + 1
            else:
                pass
            sleep(0.08)


class Clappy(StateProcess):

    def __init__(self, config):
        self.height = config.height
        self.gravity = 1
        self.max_speed = 25
        self.interval = 0.15
        self.start_position = self.height/2
        self.init()
        super(Clappy, self).__init__(config, target=self.fall, name='Clappy')

    def init(self):
        self._position = Value('i', self.start_position)
        self._falling_speed = Value('f', 0.0)
        self._instant = Value('i', 0)

    @property
    def instant(self):
        return self._instant.value

    @instant.setter
    def instant(self, instant):
        self._instant.value = instant

    @property
    def position(self):
        return self._position.value

    @position.setter
    def position(self, position):
        self._position.value = position

    @property
    def falling_speed(self):
        return self._falling_speed.value

    @falling_speed.setter
    def falling_speed(self, speed):
        self._falling_speed.value = speed

    def update_falling_speed(self):
        self.falling_speed += self.gravity * self.instant
        if (self.falling_speed >= self.max_speed):
            self.falling_speed = self.max_speed

    def update_position(self):
        self.position = int(self.position + self.falling_speed)
        if (self.position >= self.height):
            self.position = self.height - 1

    def bounce(self):
        self.log(self.position)
        if self.position == self.start_position:
            self.position = self.position + 1
        else:
            self.position = self.start_position

    def fly(self):
        self.instant = 0
        self.falling_speed = 0.0
        if self.position > 2:
            self.position = self.position - 3

    def fall(self):
        while (self.state != 4):
            if self.state == 1:
                self.bounce()
                sleep(self.interval)
            if self.state == 2:
                self.instant += 1
                self.update_position()
                self.update_falling_speed()
            sleep(self.interval)


class Config(SafeConfigParser):

    def __init__(self, conf_file=None):
        self.section = 'clappy'
        self.states = {1: 'ready', 2: 'running', 3: 'dead', 4: 'exit'}
        self.state = Value('i', 1)
        #super(Config, self).__init__()
        #if not conf_file:
        #    self.add_section(self.section)

    @property
    def height(self):
        return self.getint(self.section, 'height')

    @height.setter
    def height(self, height):
        self.set(self.section, 'height', height)

    @property
    def width(self):
        return self.getint(self.section, 'width')

    @width.setter
    def width(self, width):
        self.set(self.section, 'width', width)

    @property
    def obstacle_gap(self):
        return self.getint(self.section, 'obstacle_gap')

    @obstacle_gap.setter
    def obstacle_gap(self, obstacle_gap):
        self.set(self.section, 'obstacle_gap', obstacle_gap)


if __name__ == '__main__':

    def signal_handler(signal, frame):
        Screen.reset(None)
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    config = Config()
    config.width = 80
    config.height = 50
    config.obstacle_gap = 6
    config.state.value = 1

    clappy = Clappy(config)
    world = World(config, clappy)
    screen = Screen(config, world.world, clappy, fps=30)
    ctrl = Controller(config, screen, world)

    world.start()
    screen.start()
    ctrl.start()
    clappy.start()
