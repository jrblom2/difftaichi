import random
from math import isclose


class linkGraph:

    def __init__(self, linkSize, weights):
        self.links = []
        self.linkSize = linkSize
        self.weights = weights
        self.sides = ['bottom', 'top', 'left', 'right']
        self.links.append(link(0.0, 0.0, self.linkSize, self.linkSize, -1))
        self.loss = 0.0
        self.gen = 0
        self.num = 0

    # builds robot up to target size
    def buildToTarget(self, numLinks):
        while len(self.links) < numLinks:
            self.addRandom()

    # get correct size to adjust for in scene
    def measure(self):
        left = 0.0
        right = 0.0
        top = 0.0
        bottom = 0.0
        for link in self.links:
            if link.x < left:
                left = link.x
            if link.x > right:
                right = link.x
            if link.y > top:
                top = link.y
            if link.y < bottom:
                bottom = link.y

        return -left + 0.05, -bottom + 0.05

    # remove blocks on edges
    def remove(self, num):
        total = len(self.links)
        while len(self.links) > total - num:
            link = self.links[random.randint(0, len(self.links) - 1)]
            if self.oneAdjacent(link):
                self.links.remove(link)

    def generateRobot(self, scene):
        w, h = self.measure()
        scene.set_offset(w, h)
        for link in self.links:
            scene.add_rect(link.x, link.y, link.width, link.height, link.acctuation)
        scene.set_n_actuators(len(self.links) - 1)

    def oneAdjacent(self, newLink):
        numAdj = 0
        for item in self.links:

            if isclose(item.x, newLink.x) and isclose(item.y, newLink.y - self.linkSize):
                numAdj += 1
            if isclose(item.x, newLink.x) and isclose(item.y, newLink.y + self.linkSize):
                numAdj += 1
            if isclose(item.x, newLink.x - self.linkSize) and isclose(item.y, newLink.y):
                numAdj += 1
            if isclose(item.x, newLink.x + self.linkSize) and isclose(item.y, newLink.y):
                numAdj += 1
        if numAdj == 1:
            return True
        else:
            return False

    # randomly place a new block
    def addRandom(self):
        acctuation = len(self.links) - 1
        linkIndex = random.randint(0, len(self.links) - 1)
        oldLink = self.links[linkIndex]
        side = random.choices(self.sides, self.weights)

        match side[0]:
            case 'bottom':
                if oldLink.bottom is None:
                    newLink = link(
                        oldLink.x,
                        oldLink.y - self.linkSize,
                        self.linkSize,
                        self.linkSize,
                        acctuation,
                    )
                    if self.oneAdjacent(newLink):
                        oldLink.bottom = newLink
                        newLink.top = oldLink
                        self.links.append(newLink)
            case 'top':
                if oldLink.top is None:
                    newLink = link(
                        oldLink.x,
                        oldLink.y + self.linkSize,
                        self.linkSize,
                        self.linkSize,
                        acctuation,
                    )
                    if self.oneAdjacent(newLink):
                        oldLink.top = newLink
                        newLink.bottom = oldLink
                        self.links.append(newLink)
            case 'left':
                if oldLink.left is None:
                    newLink = link(
                        oldLink.x - self.linkSize,
                        oldLink.y,
                        self.linkSize,
                        self.linkSize,
                        acctuation,
                    )
                    if self.oneAdjacent(newLink):
                        oldLink.left = newLink
                        newLink.right = oldLink
                        self.links.append(newLink)
            case 'right':
                if oldLink.right is None:
                    newLink = link(
                        oldLink.x + self.linkSize,
                        oldLink.y,
                        self.linkSize,
                        self.linkSize,
                        acctuation,
                    )
                    if self.oneAdjacent(newLink):
                        oldLink.right = newLink
                        newLink.left = oldLink
                        self.links.append(newLink)


class link:

    def __init__(self, x, y, width, height, acctuation):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.acctuation = acctuation
        self.bottom = None
        self.top = None
        self.left = None
        self.right = None
