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

def getElementsCountAround(mesh, nodes, coordinates):
    """
    :return: elementsCountAround
    """
    apexNode = nodes.findNodeByIdentifier(1)
    elementsCountAround = 0;
    elementiterator = mesh.createElementiterator()
    element = elementiterator.next()
    while element.isValid():
        eft = element.getElementfieldtemplate(coordinates, -1)
        if eft.isValid():
            nodeCount = eft.getNumberOfLocalNodes()
            for n in range(1, nodeCount + 1):
                node = element.getNode(eft, n)
                if node == apexNode:
                    elementsCountAround += 1
                    break;
        element = elementiterator.next()
    return elementsCountAround

def getNodeIdentifiersInRow(nodes, elementsCountAround, row):
    """
    :param: row starting at 0 for apex
    :return: list of node identifiers in row
    """
    nodeIdentifiers = []
    nodeiterator = nodes.createNodeiterator()
    node = nodeiterator.next()
    remainingnodesinrow = 1
    currentRow = 0
    while node.isValid():
        if currentRow == row:
            nodeIdentifiers.append(node.getIdentifier())
        elif currentRow > row:
            break
        remainingnodesinrow -= 1
        if remainingnodesinrow == 0:
            currentRow += 1
            remainingnodesinrow = elementsCountAround
        node = nodeiterator.next()
    return nodeIdentifiers

def getMeanNodeCoordinates(fm, nodes, coordinates, nodeIdentifiers):
    xMean = [ 0.0, 0.0, 0.0 ]
    cache = fm.createFieldcache()
    for nodeIdentifier in nodeIdentifiers:
        node = nodes.findNodeByIdentifier(nodeIdentifier)
        cache.setNode(node)
        result, x = coordinates.evaluateReal(cache, 3)
        for i in range(3):
            xMean[i] += x[i]
    count = len(nodeIdentifiers);
    for i in range(3):
        xMean[i] /= count
    return xMean

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

    mesh = fm.findMeshByDimension(2)
    nodes = fm.findNodesetByFieldDomainType(Field.DOMAIN_TYPE_NODES)
    elementsCountAround = getElementsCountAround(mesh, nodes, coordinates)
    print('elementsCountAround',elementsCountAround)
    row1 = 1
    row2 = mesh.getSize() // elementsCountAround
    if row1 == row2:
        row1 = 0
    nodeIdentifiersRow1 = getNodeIdentifiersInRow(nodes, elementsCountAround, row1)
    row1centre = getMeanNodeCoordinates(fm, nodes, coordinates, nodeIdentifiersRow1)
    print('row', row1, '=', nodeIdentifiersRow1,', centre =', row1centre)
    nodeIdentifiersRow2 = getNodeIdentifiersInRow(nodes, elementsCountAround, row2)
    row2centre = getMeanNodeCoordinates(fm, nodes, coordinates, nodeIdentifiersRow2)
    print('row', row2, '=', nodeIdentifiersRow2,', centre =', row2centre)

    bottomToTop = [(row2centre[i] - row1centre[i]) for i in range(3)]
    up = vector_normalise(bottomToTop)
    forwardPoint = getMeanNodeCoordinates(fm, nodes, coordinates, nodeIdentifiersRow1[:1])
    forward = [(forwardPoint[i] - row1centre[i]) for i in range(3)]
    size = vector_magnitude(forward)
    axis = vector_cross_product3(forward, up)
    axis = vector_normalise(axis)
    forward = vector_cross_product3(up, axis)

    # create a single element plate mesh by just using xi coordinates of element 1
    plateGroup = fm.createFieldElementGroup(mesh)
    plateGroup.setName("plate")
    plateMeshGroup = plateGroup.getMeshGroup()
    element1 = mesh.findElementByIdentifier(1)
    plateMeshGroup.addElement(element1)
    plate_size = 10.0*size
    minus05 = fm.createFieldConstant([-0.5,-0.5,0.0])
    xi = fm.findFieldByName("xi")
    xiMinus05 = fm.createFieldAdd(xi, minus05)
    plateTransform = fm.createFieldConstant(axis + forward + [0.0, 0.0, 0.0])
    plateTransCoordinates = fm.createFieldMatrixMultiply(1, xiMinus05, plateTransform)
    plateCentre = [(row1centre[i] + 0.05*bottomToTop[i]) for i in range(3)]
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

    cache = fm.createFieldcache()

    result, forceValue = force.evaluateReal(cache, 1)

    print("forceValue ", result, forceValue)

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