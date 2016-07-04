#!/usr/bin/python
"""

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at http://mozilla.org/MPL/2.0/.
"""

import math
from opencmiss.zinc.context import Context as ZincContext
# from opencmiss.zinc.status import OK as ZINC_OK
# from opencmiss.zinc.element import Element, Elementbasis
from opencmiss.zinc.field import Field, FieldFindMeshLocation
from opencmiss.zinc.logger import Loggernotifier
from opencmiss.zinc.node import Node
from opencmiss.zinc.optimisation import Optimisation

def vector_cross_product3(a, b):
    """
    :param a: list of length 3
    :param b: list of length 3
    :return: list of length 3
    """
    return [a[1]*b[2] - a[2]*b[1], a[2]*b[0] - a[0]*b[2], a[0]*b[1] - a[1]*b[0]]

def vector_magnitude(v):
    """
    :param v: vector as a list
    :return: magnitude of vector
    """
    mag = 0
    for i in range(len(v)):
        mag += v[i]*v[i]
    return math.sqrt(mag)

def vector_normalise(v):
    """
    :param v: vector as a list
    :return: normalised (unit) vector as a list
    """
    mag = vector_magnitude(v)
    return [(v[i] / mag) for i in range(len(v))]

def loggerCallback(loggerEvent):
    print(loggerEvent.getMessageText())

def loadfemur(filenameIn, filenameOut):
    """
    :param filenameIn:
    :param filenameOut:
    :return: None
    """
    context = ZincContext('loadfemur')
    logger = context.getLogger()

    ln = logger.createLoggernotifier()
    ln.setCallback(loggerCallback)

    region = context.getDefaultRegion()

    region.readFile(filenameIn)
    fm = region.getFieldmodule()
    # define 3-component 'stress' field identically to coordinates
    stress = fm.findFieldByName("coordinates")
    stress.setName("stress")
    stress.setTypeCoordinate(False)
    region.readFile(filenameIn)
    coordinates = fm.findFieldByName("coordinates")

    nodes = fm.findNodesetByFieldDomainType(Field.DOMAIN_TYPE_NODES)
    node1 = nodes.findNodeByIdentifier(1)
    node5 = nodes.findNodeByIdentifier(5)

    cache = fm.createFieldcache()
    cache.setNode(node1)
    result, node1pos = coordinates.evaluateReal(cache, 3)
    cache.setNode(node5)
    result, node5pos = coordinates.evaluateReal(cache, 3)

    node15pos_delta = [(node5pos[i] - node1pos[i]) for i in range(3)]
    axis = vector_normalise(node15pos_delta)
    bottomCentre = [0.5*(node1pos[i] + node5pos[i]) for i in range(3)]

    firstTopNode = 42
    lastTopNode = 53
    nTopNodes = lastTopNode - firstTopNode + 1
    topCentre = [0.0, 0.0, 0.0]
    for ni in range(firstTopNode, lastTopNode + 1):
        node = nodes.findNodeByIdentifier(ni)
        cache.setNode(node)
        result, pos = coordinates.evaluateReal(cache, 3)
        topCentre = [(topCentre[i] + pos[i]) for i in range(3)]
    topCentre = [(topCentre[i]/nTopNodes) for i in range(3)]

    bottomToTop = [(topCentre[i] - bottomCentre[i]) for i in range(3)]
    forward = vector_normalise(vector_cross_product3(bottomToTop, axis))
    up = vector_cross_product3(axis, forward)

    # create a single element plate mesh by just using xi coordinates of element 1
    mesh = fm.findMeshByDimension(2)
    plateGroup = fm.createFieldElementGroup(mesh)
    plateGroup.setName("plate")
    plateMeshGroup = plateGroup.getMeshGroup()
    element1 = mesh.findElementByIdentifier(1)
    plateMeshGroup.addElement(element1)
    plate_size = 4.0*vector_magnitude(node15pos_delta)
    minus05 = fm.createFieldConstant([-0.5,-0.5,0.0])
    xi = fm.findFieldByName("xi")
    xiMinus05 = fm.createFieldAdd(xi, minus05)
    plateTransform = fm.createFieldConstant(axis + forward + [0.0, 0.0, 0.0])
    plateTransCoordinates = fm.createFieldMatrixMultiply(1, xiMinus05, plateTransform)
    plateCentre = [(bottomCentre[i] + 0.2*bottomToTop[i]) for i in range(3)]
    constPlateCentre = fm.createFieldConstant(plateCentre)
    plateCoordinates = fm.createFieldAdd(constPlateCentre, plateTransCoordinates)

    findXi = fm.createFieldFindMeshLocation(coordinates, plateCoordinates, plateMeshGroup)
    findXi.setSearchMode(FieldFindMeshLocation.SEARCH_MODE_NEAREST)

    projectedCoordinates = fm.createFieldEmbedded(plateCoordinates, findXi)
    # down = [-up[i] for i in range(3)]
    constUp = fm.createFieldConstant(up)
    projectionVector = fm.createFieldSubtract(projectedCoordinates, coordinates)
    negativeProjectionDistance = fm.createFieldDotProduct(projectionVector, constUp)
    constZero = fm.createFieldConstant([0.0])
    negativeProjectionDistanceIsPositive = fm.createFieldGreaterThan(negativeProjectionDistance, constZero)
    penetration = fm.createFieldIf(negativeProjectionDistanceIsPositive, negativeProjectionDistance, constZero)

    force = fm.createFieldMeshIntegral(penetration, coordinates, mesh)
    force.setNumbersOfPoints(4)

    result, forceValue = force.evaluateReal(cache, 1)

    print("forceValue 1 = " + str(forceValue))

    # for oi in range(-20, 10):
    #     plateCentre = [(bottomCentre[i] - (oi*0.2)*bottomToTop[i]) for i in range(3)]
    #     constPlateCentre.assignReal(cache, plateCentre)
    #     result, dist = negativeProjectionDistance.evaluateReal(cache, 1)
    #     result, pen = penetration.evaluateReal(cache, 1)
    #     result, coord = coordinates.evaluateReal(cache, 3)
    #     result, projCoord = projectedCoordinates.evaluateReal(cache, 3)
    #     result, forceValue = force.evaluateReal(cache, 1)
    #     print(str(oi) + ". plateCentre " + str(plateCentre) + ":  forceValue = " + str(forceValue) + " dist = " + str(dist) + " pen = " + str(pen))
    #     print("   coord = " + str(coord) + " projCoord = " + str(projCoord))

    # clear 'stress'
    stress = stress.castFiniteElement()
    nodeIter = nodes.createNodeiterator()
    node = nodeIter.next()
    zeroVector3 = [0.0, 0.0, 0.0]
    while node.isValid():
        cache.setNode(node)
        stress.setNodeParameters(cache, -1, Node.VALUE_LABEL_VALUE, 1, zeroVector3)
        stress.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS1, 1, zeroVector3)
        stress.setNodeParameters(cache, -1, Node.VALUE_LABEL_D_DS2, 1, zeroVector3)
        stress.setNodeParameters(cache, -1, Node.VALUE_LABEL_D2_DS1DS2, 1, zeroVector3)
        node = nodeIter.next()

    constZeroVector2 = fm.createFieldConstant([0.0, 0.0])
    sourceStress = fm.createFieldConcatenate([penetration, constZeroVector2])
    stressError = fm.createFieldSubtract(stress, sourceStress)
    stressFitObjective = fm.createFieldMeshIntegralSquares(stressError, coordinates, mesh)
    stressFitObjective.setNumbersOfPoints([4])
    optimisation = fm.createOptimisation()
    optimisation.setMethod(Optimisation.METHOD_LEAST_SQUARES_QUASI_NEWTON)
    optimisation.setAttributeInteger(Optimisation.ATTRIBUTE_MAXIMUM_ITERATIONS, 3)
    optimisation.addIndependentField(stress)
    optimisation.addObjectiveField(stressFitObjective)
    result = optimisation.optimise()
    print("Optimisation result = " + str(result))
    report = optimisation.getSolutionReport()

    region.writeFile(filenameOut)


def write_simpleviz_script(filename, modelfilename):
    with open(filename, 'w') as outfile:
        modelfilename = modelfilename.replace('\\', r'\\')
        outfile.write(
"""# Generated by mapclient load femur step
from opencmiss.zinc.status import OK as ZINC_OK
def loadModel(region):
    result = region.readFile(""" + '"' + modelfilename + '"' + """)
    return result == ZINC_OK
""")