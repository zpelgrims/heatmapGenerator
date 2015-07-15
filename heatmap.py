import maya.cmds as cmds
import maya.OpenMaya as api
import maya.OpenMayaUI as OpenMayaUI
import maya.mel as mel
import pymel.core as pm
import operator


#STORE VISIBLE VERTICES
def selectFromScreenApi(selectedObject, vertexMargin):
    
	#set selection mode to camera based
	mel.eval('selectPref -useDepth true;')
	
	# switch to vertex selection mode
	cmds.selectMode(component=True)
	
	#select from screen
	activeView = OpenMayaUI.M3dView.active3dView()
	api.MGlobal.selectFromScreen(0,0,activeView.portWidth(),activeView.portHeight(),api.MGlobal.kReplaceList)

	for i in range(vertexMargin):
		cmds.GrowPolygonSelectionRegion()
	
	fromScreen = cmds.ls(selection=True, flatten=True)
	
	#set selection mode back to normal
	mel.eval('selectPref -useDepth false;')
	
	#clear selection
	cmds.select(clear=True)
	cmds.selectMode(object=True)
	
	return fromScreen




# STORE POSITION OF ALL VERTICES
def vertexPositions(selectedObject):
 
	# get the active selection
	cmds.select(selectedObject)
	
	# api selection stuff
	selectedObject = api.MSelectionList()
	api.MGlobal.getActiveSelectionList( selectedObject )
	iterSel = api.MItSelectionList(selectedObject, api.MFn.kMesh)
 
	# go through selection
	while not iterSel.isDone():
 
		# get dagPath
		dagPath = api.MDagPath()
		iterSel.getDagPath( dagPath )
		
		# create empty point array
		inMeshMPointArray = api.MPointArray()
		
		# create function set and get points in world space
		currentInMeshMFnMesh = api.MFnMesh(dagPath)
		currentInMeshMFnMesh.getPoints(inMeshMPointArray, api.MSpace.kWorld)
		
		# put each point to a list
		pointList = []
		
		for i in range( inMeshMPointArray.length() ) :
			pointList.append( [inMeshMPointArray[i][0], inMeshMPointArray[i][1], inMeshMPointArray[i][2]] )
		
		return pointList
		
		


### STORE DISTANCE TO CAMERA
def distanceToCamera(cameraName, selectedObject, visibleVertices, vertexPositionList, distanceDict, distanceNode):
	
	visibleVerticesIntegers = []
	
	# extract the vertex numbers from the names
	for i in visibleVertices:
		visibleVerticesIntegers.append(int(i.split("[")[-1].split("]")[0]))
		
	counter = 0
	
	#for all vertices, write distance in dictionary
	for i in vertexPositionList:
		
		if counter in visibleVerticesIntegers:
			
			# set vertex coordinates in distance node
			cmds.setAttr((distanceNode + '.point1'), (vertexPositionList[counter][0]), (vertexPositionList[counter][1]), (vertexPositionList[counter][2]))
			
			#query distance between camera and vtx
			distance = cmds.getAttr(distanceNode + '.distance')
			
			if distanceDict.get(counter) > distance or distanceDict.get(counter) == None:
				distanceDict[counter] = distance
	
		counter = counter + 1
			
	return distanceDict



### mObject to play with API
def get_mobject(node):
	selectionList = api.MSelectionList()
	selectionList.add(node)
	oNode = api.MObject()
	selectionList.getDependNode(0, oNode)
	return oNode



### ASSIGN COLOURS TO VERTICES
def assignVertexColours(distanceDict, selectedObject):
	
	# initialize progress bar
	paintProgressBar = maya.mel.eval('$tmp = $gMainProgressBar');
	cmds.progressBar( paintProgressBar,edit=True, beginProgress=True, isInterruptable=True, status='"Painting vertices"', maxValue=len(distanceDict) )
	
	#enable vertex color display
	cmds.polyOptions(selectedObject, colorShadedDisplay = True)
	
	# select object for API stuff
	selectedObjectShape = cmds.listRelatives(selectedObject,s=True,ni=True)[0]
	selectedObjectShapeApi_Obj = get_mobject(selectedObjectShape)
	
	# make colorArray
	vertexColorList = api.MColorArray()
	
	# access and play with mesh data with MFnMesh
	meshFn = api.MFnMesh(selectedObjectShapeApi_Obj)
	
	# initialize api int array for vertices
	vertexIndexList = api.MIntArray()
	
	# append keys to api list
	for i in range(0, len(distanceDict)):
		vertexIndexList.append(distanceDict.keys()[i])
	
	#calculate max and min distance
	maxDistanceKey = max(distanceDict.iteritems(), key=operator.itemgetter(1))[0]
	minDistanceKey = min(distanceDict.iteritems(), key=operator.itemgetter(1))[0]
	maxDistance = distanceDict.get(maxDistanceKey)
	minDistance = distanceDict.get(minDistanceKey)
	
	#normalize variables
	normalizedDistanceDict = {}
	OldRange = (maxDistance - minDistance)  
	NewRange = (1 - 0)
	
	for i in range(0,len(distanceDict)):
	
		# normalize values
		newValue = (((distanceDict.values()[i] - minDistance) * NewRange) / OldRange)
		
		# sample colour at point in ramp
		colourAtPoint = cmds.colorAtPoint(colourRamp, o="RGB",u = newValue, v = 0.5)
		
		# append colour values to api colour list
		vertexColorList.append(colourAtPoint[0], colourAtPoint[1], colourAtPoint[2])
		
		# enable the progress to be cancelled
		if cmds.progressBar(paintProgressBar, query=True, isCancelled=True) == True:
			break
		
		# progress bar step forward	
		cmds.progressBar(paintProgressBar, edit=True, step=100)
				
	# write all vertexColor in one operation
	meshFn.setVertexColors(vertexColorList, vertexIndexList, None )
	
	# end progress bar
	cmds.progressBar(paintProgressBar, edit=True, endProgress=True)




## FOR EVERY FRAME 
def cameraPainter(selectedObject, selectedCameras, frameRanges, vertexMargin, byFrameList):
	
	counter = 0
	distanceDict = {}
	
	#Create distance node
	distanceNode = cmds.shadingNode('distanceBetween', name = 'distanceNode', asUtility = 1)
	
	# create a list with vertex positions of all vertices
	vertexPositionList = vertexPositions(selectedObject)
	
	#initialise distance progress bar
	distanceProgressBar = maya.mel.eval('$tmp = $gMainProgressBar');
	cmds.progressBar(distanceProgressBar,edit=True, beginProgress=True, isInterruptable=True, status='"Calculating distances"', maxValue=frameRangeCheck(frameRanges))
	
	for i in selectedCameras:
		
		# change camera
		cameraName = str(selectedCameras[counter])
		cmds.lookThru(cameraName)
		
		# set time to startFrame
		cmds.currentTime(frameRanges[counter][0], edit=True )
		
		print distanceNode
		cmds.connectAttr((cameraName + '.worldMatrix'), (distanceNode + '.inMatrix2'), force=True)
		
		#for every frame
		for i in range(frameRanges[counter][0], frameRanges[counter][1]):
			
			# query visible vertices
			visibleVertices =  selectFromScreenApi(selectedObject, vertexMargin)
			
			# calculate distance
			distanceDict = distanceToCamera(cameraName, selectedObject, visibleVertices, vertexPositionList, distanceDict, distanceNode)
			
			#step forward a frame
			mel.eval('playButtonStepForward;')
			
			# progressbar interrupt
			if cmds.progressBar(distanceProgressBar, query=True, isCancelled=True ):
				break
			
			#progressbar step forward
			cmds.progressBar(distanceProgressBar, edit=True, step=1)
		
		# flush undo history to remove ram usage of script
		cmds.flushUndo()
		
		counter += 1
		
		#progressbar interrupt (extra one for parent loop)
		if cmds.progressBar(distanceProgressBar, query=True, isCancelled=True ):
			break
			
	# progressbar end
	cmds.progressBar(distanceProgressBar, edit=True, endProgress=True)
	
	# assign vertex colours
	assignVertexColours(distanceDict, selectedObject)
	



def frameRangeCheck(frameRanges):
	
	if len(frameRanges) == 1:
		frameRangeValue = [x[1] - x[0] for x in frameRanges][0]
		
	else:
		frameRangeValue = [x[1] - x[0] for x in frameRanges][0] + [x[1] - x[0] for x in frameRanges][1]
	
	return frameRangeValue
		
		
		
		
def floodVertices(selectedObject, colourValue):
	
	cmds.polyOptions(selectedObject, colorShadedDisplay = True)
	cmds.select(selectedObject)
	cmds.polyColorPerVertex( r=colourValue[0], g=colourValue[1], b=colourValue[2] )
	
	
	
	
def invisibleColor(*args):
	
	cmds.colorEditor()
	
	if cmds.colorEditor(query=True, result=True):
		invisibleColorValue = cmds.colorEditor(query=True, rgb=True)
	
	return invisibleColorValue



		
def rampPresetChange(*args):
	
	presetName = cmds.optionMenu(rampPresets, query=True, value=True)
	
	if presetName == "Zbrush Remesh":
		
		for i in range(2,4):
			
			cmds.removeMultiInstance(colourRamp + '.colorEntryList[' + str(i) + ']', b=True)
		
		cmds.setAttr(colourRamp + '.colorEntryList[0].color', 1, 0, 0, type ="double3")
		cmds.setAttr(colourRamp + '.colorEntryList[0].position', 0)
		
		cmds.setAttr(colourRamp + '.colorEntryList[2].position', 0.5)
		cmds.setAttr(colourRamp + '.colorEntryList[2].color', 1, 1, 1, type ="double3")
		
		cmds.setAttr(colourRamp + '.colorEntryList[1].position', 1)
		cmds.setAttr(colourRamp + '.colorEntryList[1].color', 0, 0, 1, type ="double3")
		
	
	if presetName == "Heat Map":
		
		cmds.setAttr(colourRamp + '.colorEntryList[4].color', 0.192, 0.024, 0.580, type ="double3")
		cmds.setAttr(colourRamp + '.colorEntryList[4].position', 1.0)
		
		cmds.setAttr(colourRamp + '.colorEntryList[3].position', 0.75)
		cmds.setAttr(colourRamp + '.colorEntryList[3].color', 0.533, 0.004, 0.710, type ="double3")
		
		cmds.setAttr(colourRamp + '.colorEntryList[2].position', 0.5)
		cmds.setAttr(colourRamp + '.colorEntryList[2].color', 0.961, 0.329, 0.149, type ="double3")
		
		cmds.setAttr(colourRamp + '.colorEntryList[1].position', 0.25)
		cmds.setAttr(colourRamp + '.colorEntryList[1].color', 0.976, 0.694, 0.016, type ="double3")
		
		cmds.setAttr(colourRamp + '.colorEntryList[0].position', 0)
		cmds.setAttr(colourRamp + '.colorEntryList[0].color', 1, 1, 1, type ="double3")
	
	if presetName == "Custom":
		
		for i in range(0,4):
			cmds.removeMultiInstance(colourRamp + '.colorEntryList[' + str(i) + ']', b=True)
		
		cmds.setAttr(colourRamp + '.colorEntryList[0].position', 0)
		cmds.setAttr(colourRamp + '.colorEntryList[0].color', 1, 1, 1, type ="double3")

		cmds.setAttr(colourRamp + '.colorEntryList[1].position', 1)
		cmds.setAttr(colourRamp + '.colorEntryList[1].color', 0, 0, 0, type ="double3")

	
def selectBaseObject(selectedObject):
	if len(selectedObject) == 0:
		cmds.textField("baseObject", e=True, tx="Please select an object")
		api.MGlobal.displayError("Select an object")
	elif len(selectedObject) > 1:
		cmds.textField("baseObject", e=True, tx="Please select only one object")
		api.MGlobal.displayError("Please select only one object")
	else:
		cmds.textField("baseObject", e=True, tx=selectedObject[0])
	

	
def selectBaseObjectButton(*args):
	# variables
	selectedObject = cmds.ls(sl=True, tr=True)

	# call selectBaseObject function
	selectBaseObject(selectedObject)
	

def vtxMapButton(*args):
	return


def executeButton(*args):
	
	selectedObject = cmds.textField("baseObject", query=True, tx=True)
	vertexMargin = cmds.intSliderGrp("vertexMargin", query=True, v=True)

	selectedCameras = []
	frameRanges = []
	
	if len(allShots) == 0:
		api.MGlobal.displayError("You must have a shot sequence")
		return
		
		
	for i in range(1, len(allShots) + 1 ):
		if cmds.checkBox("checkBox_"+str(i), query=True, value=True) == 1:
			selectedCameras.append(cmds.text("cameraName_"+str(i), query=True, l=True))
			frameRanges.append([int(cmds.textField("startFrameField_" + str(i), query=True, tx=True)), int(cmds.textField("endFrameField_" + str(i), query=True, tx=True))+1])
			
	print selectedCameras
	print frameRanges
	
	# FIX THIS LIST TO HAVE VALUES!!!
	byFrameList = []
	
	# call function
	cameraPainter(selectedObject, selectedCameras, frameRanges, vertexMargin, byFrameList)
	
	
	
def floodButton(*args):
	# variables
	selectedObject = cmds.textField("baseObject", query=True, tx=True)
	# call selectBaseObject function
	
	colourValue  = invisibleColor()
	floodVertices(selectedObject, colourValue)
		

		
def selectColourRamp(*args):
	cmds.select(colourRamp)


	
def windowUI(*args):
	
	# gather cameras
	global allShots
	allShots = cmds.sequenceManager(lsh=True)
	
	if allShots == None:
		api.MGlobal.displayError("You must have a shot sequence")
		return
	
	global colourRamp
	colourRamp = cmds.createNode('ramp', name="colourRamp")
	cmds.setAttr(colourRamp + '.colorEntryList[0].position', 0)
	cmds.setAttr(colourRamp + '.colorEntryList[0].color', 1, 1, 1, type ="double3")
	cmds.setAttr(colourRamp + '.colorEntryList[1].position', 1)
	cmds.setAttr(colourRamp + '.colorEntryList[1].color', 0, 0, 0, type ="double3")
	cmds.setAttr(colourRamp + ".type", 1)

	# create the window
	if cmds.window("windowUI", exists=True):
		cmds.deleteUI("windowUI")
	cmds.window("windowUI", title="Camera Painter v1.1", resizeToFitChildren=True, sizeable = True)
	
	# header image
	#cmds.rowColumnLayout(w=400)
	#cmds.image(image="cameraPainter_header.png")
	#cmds.setParent("..")
	
	
	# object select layout
	cmds.frameLayout(label = "Options", collapsable=False, mw=7, mh=7)
	cmds.rowColumnLayout(nc=3, cal=[(1,"right")], cw=[(1,110),(2,425),(3,95)])
	cmds.text(l="Base Object:   ")
	cmds.textField("baseObject")
	cmds.button("baseObjectButton", l="Select", c=selectBaseObjectButton)
	cmds.setParent("..")
	cmds.separator(h=10, st='in')
	
	
	
	# camera select layout
	cmds.rowColumnLayout(nc=8, cal=[(1,"left")], cw=[(1,20),(2,250),(3,80), (4,40), (5,80), (6,40), (7,80), (8,40)])
	
	global checkBox_1, cameraName_1, startFrame_1, startFrameField_1, endFrame_1, endFrameField_1, byFrame_1, byFrameField_1
	global checkBox_2, cameraName_2, startFrame_2, startFrameField_2, endFrame_2, endFrameField_2, byFrame_2, byFrameField_2
	global checkBox_3, cameraName_3, startFrame_3, startFrameField_3, endFrame_3, endFrameField_3, byFrame_3, byFrameField_3
	global checkBox_4, cameraName_4, startFrame_4, startFrameField_4, endFrame_4, endFrameField_4, byFrame_4, byFrameField_4
	global checkBox_6, cameraName_6, startFrame_6, startFrameField_6, endFrame_6, endFrameField_6, byFrame_6, byFrameField_6
	global checkBox_7, cameraName_7, startFrame_7, startFrameField_7, endFrame_7, endFrameField_7, byFrame_7, byFrameField_7
	global checkBox_8, cameraName_8, startFrame_8, startFrameField_8, endFrame_8, endFrameField_8, byFrame_8, byFrameField_8
	global checkBox_9, cameraName_9, startFrame_9, startFrameField_9, endFrame_9, endFrameField_9, byFrame_9, byFrameField_9
	global checkBox_10, cameraName_10, startFrame_10, startFrameField_10, endFrame_10, endFrameField_10, byFrame_10, byFrameField_10
	global checkBox_11, cameraName_11, startFrame_11, startFrameField_11, endFrame_11, endFrameField_11, byFrame_11, byFrameField_11
	global checkBox_12, cameraName_12, startFrame_12, startFrameField_12, endFrame_12, endFrameField_12, byFrame_12, byFrameField_12
	global checkBox_13, cameraName_13, startFrame_13, startFrameField_13, endFrame_13, endFrameField_13, byFrame_13, byFrameField_13
	global checkBox_14, cameraName_14, startFrame_14, startFrameField_14, endFrame_14, endFrameField_14, byFrame_14, byFrameField_14
	global checkBox_15, cameraName_15, startFrame_15, startFrameField_15, endFrame_15, endFrameField_15, byFrame_15, byFrameField_15
	global checkBox_16, cameraName_16, startFrame_16, startFrameField_16, endFrame_16, endFrameField_16, byFrame_16, byFrameField_16
	global checkBox_17, cameraName_17, startFrame_17, startFrameField_17, endFrame_17, endFrameField_17, byFrame_17, byFrameField_17
	global checkBox_18, cameraName_18, startFrame_18, startFrameField_18, endFrame_18, endFrameField_18, byFrame_18, byFrameField_18
	global checkBox_19, cameraName_19, startFrame_19, startFrameField_19, endFrame_19, endFrameField_19, byFrame_19, byFrameField_19
	global checkBox_20, cameraName_20, startFrame_20, startFrameField_20, endFrame_20, endFrameField_20, byFrame_20, byFrameField_20
	global checkBox_21, cameraName_21, startFrame_21, startFrameField_21, endFrame_21, endFrameField_21, byFrame_21, byFrameField_21
	global checkBox_22, cameraName_22, startFrame_22, startFrameField_22, endFrame_22, endFrameField_22, byFrame_22, byFrameField_22
	global checkBox_23, cameraName_23, startFrame_23, startFrameField_23, endFrame_23, endFrameField_23, byFrame_23, byFrameField_23
	global checkBox_24, cameraName_24, startFrame_24, startFrameField_24, endFrame_24, endFrameField_24, byFrame_24, byFrameField_24
	global checkBox_25, cameraName_25, startFrame_25, startFrameField_25, endFrame_25, endFrameField_25, byFrame_25, byFrameField_25
	global checkBox_26, cameraName_26, startFrame_26, startFrameField_26, endFrame_26, endFrameField_26, byFrame_26, byFrameField_26
	global checkBox_27, cameraName_27, startFrame_27, startFrameField_27, endFrame_27, endFrameField_27, byFrame_27, byFrameField_27
	global checkBox_28, cameraName_28, startFrame_28, startFrameField_28, endFrame_28, endFrameField_28, byFrame_28, byFrameField_28
	global checkBox_29, cameraName_29, startFrame_29, startFrameField_29, endFrame_29, endFrameField_29, byFrame_29, byFrameField_29
	global checkBox_30, cameraName_30, startFrame_30, startFrameField_30, endFrame_30, endFrameField_30, byFrame_30, byFrameField_30
	global checkBox_31, cameraName_31, startFrame_31, startFrameField_31, endFrame_31, endFrameField_31, byFrame_31, byFrameField_31
	global checkBox_32, cameraName_32, startFrame_32, startFrameField_32, endFrame_32, endFrameField_32, byFrame_32, byFrameField_32
	global checkBox_33, cameraName_33, startFrame_33, startFrameField_33, endFrame_33, endFrameField_33, byFrame_33, byFrameField_33
	global checkBox_34, cameraName_34, startFrame_34, startFrameField_34, endFrame_34, endFrameField_34, byFrame_34, byFrameField_34
	global checkBox_35, cameraName_35, startFrame_35, startFrameField_35, endFrame_35, endFrameField_35, byFrame_35, byFrameField_35
	global checkBox_36, cameraName_36, startFrame_36, startFrameField_36, endFrame_36, endFrameField_36, byFrame_36, byFrameField_36
	global checkBox_37, cameraName_37, startFrame_37, startFrameField_37, endFrame_37, endFrameField_37, byFrame_37, byFrameField_37
	global checkBox_38, cameraName_38, startFrame_38, startFrameField_38, endFrame_38, endFrameField_38, byFrame_38, byFrameField_38
	global checkBox_39, cameraName_39, startFrame_39, startFrameField_39, endFrame_39, endFrameField_39, byFrame_39, byFrameField_39
	global checkBox_40, cameraName_40, startFrame_40, startFrameField_40, endFrame_40, endFrameField_40, byFrame_40, byFrameField_40
	
	

	if len(allShots) >= 1:
		checkBox_1 = cmds.checkBox("checkBox_1", l="", value=1)
		cameraName_1 = cmds.text("cameraName_1", l=cmds.shot(allShots[0], query=True, currentCamera = True))
		startFrame_1 = cmds.text(l="Start Frame:  ")
		startFrameField_1 = cmds.textField("startFrameField_1", it=int(cmds.shot(allShots[0], query=True, startTime = True)))
		endFrame_1 = cmds.text(l="End Frame:")
		endFrameField_1 = cmds.textField("endFrameField_1", it=int(cmds.shot(allShots[0], query=True, endTime = True)))
		byFrame_1 = cmds.text(l="By Frame:")
		byFrameField_1 = cmds.textField("byFrameField_1", en=False)
		
	if len(allShots) >= 2:
		checkBox_2 = cmds.checkBox("checkBox_2", l="", value=1)
		cameraName_2 = cmds.text("cameraName_2", l=cmds.shot(allShots[1], query=True, currentCamera = True))
		startFrame_2 = cmds.text(l="Start Frame:  ")
		startFrameField_2 = cmds.textField("startFrameField_2", it=int(cmds.shot(allShots[1], query=True, startTime = True)))
		endFrame_2 = cmds.text(l="End Frame:")
		endFrameField_2 = cmds.textField("endFrameField_2", it=int(cmds.shot(allShots[1], query=True, endTime = True)))
		byFrame_2 = cmds.text(l="By Frame:")
		byFrameField_2 = cmds.textField("byFrameField_2", en=False)
	
	if len(allShots) >= 3:
		checkBox_3 = cmds.checkBox("checkBox_3", l="", value=1)
		cameraName_3 = cmds.text("cameraName_3", l=cmds.shot(allShots[2], query=True, currentCamera = True))
		startFrame_3 = cmds.text(l="Start Frame:  ")
		startFrameField_3 = cmds.textField("startFrameField_3", it=int(cmds.shot(allShots[2], query=True, startTime = True)))
		endFrame_3 = cmds.text(l="End Frame:")
		endFrameField_3 = cmds.textField("endFrameField_3", it=int(cmds.shot(allShots[2], query=True, endTime = True)))
		byFrame_3 = cmds.text(l="By Frame:")
		byFrameField_3 = cmds.textField("byFrameField_3", en=False)
		
	if len(allShots) >= 4:
		checkBox_4 = cmds.checkBox("checkBox_4", l="", value=1)
		cameraName_4 = cmds.text("cameraName_4", l=cmds.shot(allShots[3], query=True, currentCamera = True))
		startFrame_4 = cmds.text(l="Start Frame:  ")
		startFrameField_4 = cmds.textField("startFrameField_4", it=int(cmds.shot(allShots[3], query=True, startTime = True)))
		endFrame_4 = cmds.text(l="End Frame:")
		endFrameField_4 = cmds.textField("endFrameField_4", it=int(cmds.shot(allShots[3], query=True, endTime = True)))
		byFrame_4 = cmds.text(l="By Frame:")
		byFrameField_4 = cmds.textField("byFrameField_4", en=False)
		
	if len(allShots) >= 5:
		checkBox_5 = cmds.checkBox("checkBox_5", l="", value=1)
		cameraName_5 = cmds.text("cameraName_5", l=cmds.shot(allShots[4], query=True, currentCamera = True))
		startFrame_5 = cmds.text(l="Start Frame:  ")
		startFrameField_5 = cmds.textField("startFrameField_5", it=int(cmds.shot(allShots[4], query=True, startTime = True)))
		endFrame_5 = cmds.text(l="End Frame:")
		endFrameField_5 = cmds.textField("endFrameField_5", it=int(cmds.shot(allShots[4], query=True, endTime = True)))
		byFrame_5 = cmds.text(l="By Frame:")
		byFrameField_5 = cmds.textField("byFrameField_5", en=False)
	
	if len(allShots) >= 6:
		checkBox_6 = cmds.checkBox("checkBox_6", l="", value=1)
		cameraName_6 = cmds.text("cameraName_6", l=cmds.shot(allShots[5], query=True, currentCamera = True))
		startFrame_6 = cmds.text(l="Start Frame:  ")
		startFrameField_6 = cmds.textField("startFrameField_6", it=int(cmds.shot(allShots[5], query=True, startTime = True)))
		endFrame_6 = cmds.text(l="End Frame:")
		endFrameField_6 = cmds.textField("endFrameField_6", it=int(cmds.shot(allShots[5], query=True, endTime = True)))
		byFrame_6 = cmds.text(l="By Frame:")
		byFrameField_6 = cmds.textField("byFrameField_6", en=False)
		
	if len(allShots) >= 7:
		checkBox_7 = cmds.checkBox("checkBox_7", l="", value=1)
		cameraName_7 = cmds.text("cameraName_7", l=cmds.shot(allShots[6], query=True, currentCamera = True))
		startFrame_7 = cmds.text(l="Start Frame:  ")
		startFrameField_7 = cmds.textField("startFrameField_7", it=int(cmds.shot(allShots[6], query=True, startTime = True)))
		endFrame_7 = cmds.text(l="End Frame:")
		endFrameField_7 = cmds.textField("endFrameField_7", it=int(cmds.shot(allShots[6], query=True, endTime = True)))
		byFrame_7 = cmds.text(l="By Frame:")
		byFrameField_7 = cmds.textField("byFrameField_7", en=False)
	
	if len(allShots) >= 8:
		checkBox_8 = cmds.checkBox("checkBox_8", l="", value=1)
		cameraName_8 = cmds.text("cameraName_8", l=cmds.shot(allShots[7], query=True, currentCamera = True))
		startFrame_8 = cmds.text(l="Start Frame:  ")
		startFrameField_8 = cmds.textField("startFrameField_8", it=int(cmds.shot(allShots[7], query=True, startTime = True)))
		endFrame_8 = cmds.text(l="End Frame:")
		endFrameField_8 = cmds.textField("endFrameField_8", it=int(cmds.shot(allShots[7], query=True, endTime = True)))
		byFrame_8 = cmds.text(l="By Frame:")
		byFrameField_8 = cmds.textField("byFrameField_8", en=False)
		
	if len(allShots) >= 9:
		checkBox_9 = cmds.checkBox("checkBox_9", l="", value=1)
		cameraName_9 = cmds.text("cameraName_9", l=cmds.shot(allShots[8], query=True, currentCamera = True))
		startFrame_9 = cmds.text(l="Start Frame:  ")
		startFrameField_9 = cmds.textField("startFrameField_9", it=int(cmds.shot(allShots[8], query=True, startTime = True)))
		endFrame_9 = cmds.text(l="End Frame:")
		endFrameField_9 = cmds.textField("endFrameField_9", it=int(cmds.shot(allShots[8], query=True, endTime = True)))
		byFrame_9 = cmds.text(l="By Frame:")
		byFrameField_9 = cmds.textField("byFrameField_9", en=False)
	
	if len(allShots) >= 10:
		checkBox_10 = cmds.checkBox("checkBox_10", l="", value=1)
		cameraName_10 = cmds.text("cameraName_10", l=cmds.shot(allShots[9], query=True, currentCamera = True))
		startFrame_10 = cmds.text(l="Start Frame:  ")
		startFrameField_10 = cmds.textField("startFrameField_10", it=int(cmds.shot(allShots[9], query=True, startTime = True)))
		endFrame_10 = cmds.text(l="End Frame:")
		endFrameField_10 = cmds.textField("endFrameField_10", it=int(cmds.shot(allShots[9], query=True, endTime = True)))
		byFrame_10 = cmds.text(l="By Frame:")
		byFrameField_10 = cmds.textField("byFrameField_10", en=False)
		
	if len(allShots) >= 11:
		checkBox_11 = cmds.checkBox("checkBox_11", l="", value=1)
		cameraName_11 = cmds.text("cameraName_11", l=cmds.shot(allShots[10], query=True, currentCamera = True))
		startFrame_11 = cmds.text(l="Start Frame:  ")
		startFrameField_11 = cmds.textField("startFrameField_11", it=int(cmds.shot(allShots[10], query=True, startTime = True)))
		endFrame_11 = cmds.text(l="End Frame:")
		endFrameField_11 = cmds.textField("endFrameField_11", it=int(cmds.shot(allShots[10], query=True, endTime = True)))
		byFrame_11 = cmds.text(l="By Frame:")
		byFrameField_11 = cmds.textField("byFrameField_11", en=False)
		
	if len(allShots) >= 12:
		checkBox_12 = cmds.checkBox("checkBox_12", l="", value=1)
		cameraName_12 = cmds.text("cameraName_12", l=cmds.shot(allShots[11], query=True, currentCamera = True))
		startFrame_12 = cmds.text(l="Start Frame:  ")
		startFrameField_12 = cmds.textField("startFrameField_12", it=int(cmds.shot(allShots[11], query=True, startTime = True)))
		endFrame_12 = cmds.text(l="End Frame:")
		endFrameField_12 = cmds.textField("endFrameField_12", it=int(cmds.shot(allShots[11], query=True, endTime = True)))
		byFrame_12 = cmds.text(l="By Frame:")
		byFrameField_12 = cmds.textField("byFrameField_12", en=False)
		
	if len(allShots) >= 13:
		checkBox_13 = cmds.checkBox("checkBox_13", l="", value=1)
		cameraName_13 = cmds.text("cameraName_13", l=cmds.shot(allShots[12], query=True, currentCamera = True))
		startFrame_13 = cmds.text(l="Start Frame:  ")
		startFrameField_13 = cmds.textField("startFrameField_13", it=int(cmds.shot(allShots[12], query=True, startTime = True)))
		endFrame_13 = cmds.text(l="End Frame:")
		endFrameField_13 = cmds.textField("endFrameField_13", it=int(cmds.shot(allShots[12], query=True, endTime = True)))
		byFrame_13 = cmds.text(l="By Frame:")
		byFrameField_13 = cmds.textField("byFrameField_13", en=False)
		
	if len(allShots) >= 14:
		checkBox_14 = cmds.checkBox("checkBox_14", l="", value=1)
		cameraName_14 = cmds.text("cameraName_14", l=cmds.shot(allShots[13], query=True, currentCamera = True))
		startFrame_14 = cmds.text(l="Start Frame:  ")
		startFrameField_14 = cmds.textField("startFrameField_14", it=int(cmds.shot(allShots[13], query=True, startTime = True)))
		endFrame_14 = cmds.text(l="End Frame:")
		endFrameField_14 = cmds.textField("endFrameField_14", it=int(cmds.shot(allShots[13], query=True, endTime = True)))
		byFrame_14 = cmds.text(l="By Frame:")
		byFrameField_14 = cmds.textField("byFrameField_14", en=False)
		
	if len(allShots) >= 15:
		checkBox_15 = cmds.checkBox("checkBox_15", l="", value=1)
		cameraName_15 = cmds.text("cameraName_15", l=cmds.shot(allShots[14], query=True, currentCamera = True))
		startFrame_15 = cmds.text(l="Start Frame:  ")
		startFrameField_15 = cmds.textField("startFrameField_15", it=int(cmds.shot(allShots[14], query=True, startTime = True)))
		endFrame_15 = cmds.text(l="End Frame:")
		endFrameField_15 = cmds.textField("endFrameField_15", it=int(cmds.shot(allShots[14], query=True, endTime = True)))
		byFrame_15 = cmds.text(l="By Frame:")
		byFrameField_15 = cmds.textField("byFrameField_15", en=False)
		
	if len(allShots) >= 16:
		checkBox_16 = cmds.checkBox("checkBox_16", l="", value=1)
		cameraName_16 = cmds.text("cameraName_16", l=cmds.shot(allShots[15], query=True, currentCamera = True))
		startFrame_16 = cmds.text(l="Start Frame:  ")
		startFrameField_16 = cmds.textField("startFrameField_16", it=int(cmds.shot(allShots[15], query=True, startTime = True)))
		endFrame_16 = cmds.text(l="End Frame:")
		endFrameField_16 = cmds.textField("endFrameField_16", it=int(cmds.shot(allShots[15], query=True, endTime = True)))
		byFrame_16 = cmds.text(l="By Frame:")
		byFrameField_16 = cmds.textField("byFrameField_16", en=False)
		
	if len(allShots) >= 17:
		checkBox_17 = cmds.checkBox("checkBox_17", l="", value=1)
		cameraName_17 = cmds.text("cameraName_17", l=cmds.shot(allShots[16], query=True, currentCamera = True))
		startFrame_17 = cmds.text(l="Start Frame:  ")
		startFrameField_17 = cmds.textField("startFrameField_17", it=int(cmds.shot(allShots[16], query=True, startTime = True)))
		endFrame_17 = cmds.text(l="End Frame:")
		endFrameField_17 = cmds.textField("endFrameField_17", it=int(cmds.shot(allShots[16], query=True, endTime = True)))
		byFrame_17 = cmds.text(l="By Frame:")
		byFrameField_17 = cmds.textField("byFrameField_17", en=False)
		
	if len(allShots) >= 18:
		checkBox_18 = cmds.checkBox("checkBox_18", l="", value=1)
		cameraName_18 = cmds.text("cameraName_18", l=cmds.shot(allShots[17], query=True, currentCamera = True))
		startFrame_18 = cmds.text(l="Start Frame:  ")
		startFrameField_18 = cmds.textField("startFrameField_18", it=int(cmds.shot(allShots[17], query=True, startTime = True)))
		endFrame_18 = cmds.text(l="End Frame:")
		endFrameField_18 = cmds.textField("endFrameField_18", it=int(cmds.shot(allShots[17], query=True, endTime = True)))
		byFrame_18 = cmds.text(l="By Frame:")
		byFrameField_18 = cmds.textField("byFrameField_18", en=False)
		
	if len(allShots) >= 19:
		checkBox_19 = cmds.checkBox("checkBox_19", l="", value=1)
		cameraName_19 = cmds.text("cameraName_19", l=cmds.shot(allShots[18], query=True, currentCamera = True))
		startFrame_19 = cmds.text(l="Start Frame:  ")
		startFrameField_19 = cmds.textField("startFrameField_19", it=int(cmds.shot(allShots[18], query=True, startTime = True)))
		endFrame_19 = cmds.text(l="End Frame:")
		endFrameField_19 = cmds.textField("endFrameField_19", it=int(cmds.shot(allShots[18], query=True, endTime = True)))
		byFrame_19 = cmds.text(l="By Frame:")
		byFrameField_19 = cmds.textField("byFrameField_19", en=False)
	
	if len(allShots) >= 20:
		checkBox_20 = cmds.checkBox("checkBox_20", l="", value=1)
		cameraName_20 = cmds.text("cameraName_20", l=cmds.shot(allShots[19], query=True, currentCamera = True))
		startFrame_20 = cmds.text(l="Start Frame:  ")
		startFrameField_20 = cmds.textField("startFrameField_20", it=int(cmds.shot(allShots[19], query=True, startTime = True)))
		endFrame_20 = cmds.text(l="End Frame:")
		endFrameField_20 = cmds.textField("endFrameField_20", it=int(cmds.shot(allShots[19], query=True, endTime = True)))
		byFrame_20 = cmds.text(l="By Frame:")
		byFrameField_20 = cmds.textField("byFrameField_20", en=False)
		
	if len(allShots) >= 21:
		checkBox_21 = cmds.checkBox("checkBox_21", l="", value=1)
		cameraName_21 = cmds.text("cameraName_21", l=cmds.shot(allShots[20], query=True, currentCamera = True))
		startFrame_21 = cmds.text(l="Start Frame:  ")
		startFrameField_21 = cmds.textField("startFrameField_21", it=int(cmds.shot(allShots[20], query=True, startTime = True)))
		endFrame_21 = cmds.text(l="End Frame:")
		endFrameField_21 = cmds.textField("endFrameField_21", it=int(cmds.shot(allShots[20], query=True, endTime = True)))
		byFrame_21 = cmds.text(l="By Frame:")
		byFrameField_21 = cmds.textField("byFrameField_21", en=False)
	
	if len(allShots) >= 22:
		checkBox_22 = cmds.checkBox("checkBox_22", l="", value=1)
		cameraName_22 = cmds.text("cameraName_22", l=cmds.shot(allShots[21], query=True, currentCamera = True))
		startFrame_22 = cmds.text(l="Start Frame:  ")
		startFrameField_22 = cmds.textField("startFrameField_22", it=int(cmds.shot(allShots[21], query=True, startTime = True)))
		endFrame_22 = cmds.text(l="End Frame:")
		endFrameField_22 = cmds.textField("endFrameField_22", it=int(cmds.shot(allShots[21], query=True, endTime = True)))
		byFrame_22 = cmds.text(l="By Frame:")
		byFrameField_22 = cmds.textField("byFrameField_22", en=False)

	if len(allShots) >= 23:
		checkBox_23 = cmds.checkBox("checkBox_23", l="", value=1)
		cameraName_23 = cmds.text("cameraName_23", l=cmds.shot(allShots[22], query=True, currentCamera = True))
		startFrame_23 = cmds.text(l="Start Frame:  ")
		startFrameField_23 = cmds.textField("startFrameField_23", it=int(cmds.shot(allShots[22], query=True, startTime = True)))
		endFrame_23 = cmds.text(l="End Frame:")
		endFrameField_23 = cmds.textField("endFrameField_23", it=int(cmds.shot(allShots[22], query=True, endTime = True)))
		byFrame_23 = cmds.text(l="By Frame:")
		byFrameField_23 = cmds.textField("byFrameField_23", en=False)

	if len(allShots) >= 24:
		checkBox_24 = cmds.checkBox("checkBox_24", l="", value=1)
		cameraName_24 = cmds.text("cameraName_24", l=cmds.shot(allShots[23], query=True, currentCamera = True))
		startFrame_24 = cmds.text(l="Start Frame:  ")
		startFrameField_24 = cmds.textField("startFrameField_24", it=int(cmds.shot(allShots[23], query=True, startTime = True)))
		endFrame_24 = cmds.text(l="End Frame:")
		endFrameField_24 = cmds.textField("endFrameField_24", it=int(cmds.shot(allShots[23], query=True, endTime = True)))
		byFrame_24 = cmds.text(l="By Frame:")
		byFrameField_24 = cmds.textField("byFrameField_24", en=False)
		
	
	if len(allShots) >= 25:
		checkBox_25 = cmds.checkBox("checkBox_25", l="", value=1)
		cameraName_25 = cmds.text("cameraName_25", l=cmds.shot(allShots[24], query=True, currentCamera = True))
		startFrame_25 = cmds.text(l="Start Frame:  ")
		startFrameField_25 = cmds.textField("startFrameField_25", it=int(cmds.shot(allShots[24], query=True, startTime = True)))
		endFrame_25 = cmds.text(l="End Frame:")
		endFrameField_25 = cmds.textField("endFrameField_25", it=int(cmds.shot(allShots[24], query=True, endTime = True)))
		byFrame_25 = cmds.text(l="By Frame:")
		byFrameField_25 = cmds.textField("byFrameField_25", en=False)
	
	if len(allShots) >= 26:
		checkBox_26 = cmds.checkBox("checkBox_26", l="", value=1)
		cameraName_26 = cmds.text("cameraName_26", l=cmds.shot(allShots[25], query=True, currentCamera = True))
		startFrame_26 = cmds.text(l="Start Frame:  ")
		startFrameField_26 = cmds.textField("startFrameField_26", it=int(cmds.shot(allShots[25], query=True, startTime = True)))
		endFrame_26 = cmds.text(l="End Frame:")
		endFrameField_26 = cmds.textField("endFrameField_26", it=int(cmds.shot(allShots[25], query=True, endTime = True)))
		byFrame_26 = cmds.text(l="By Frame:")
		byFrameField_26 = cmds.textField("byFrameField_26", en=False)
	
	if len(allShots) >= 27:
		checkBox_27 = cmds.checkBox("checkBox_27", l="", value=1)
		cameraName_27 = cmds.text("cameraName_27", l=cmds.shot(allShots[26], query=True, currentCamera = True))
		startFrame_27 = cmds.text(l="Start Frame:  ")
		startFrameField_27 = cmds.textField("startFrameField_27", it=int(cmds.shot(allShots[26], query=True, startTime = True)))
		endFrame_27 = cmds.text(l="End Frame:")
		endFrameField_27 = cmds.textField("endFrameField_27", it=int(cmds.shot(allShots[26], query=True, endTime = True)))
		byFrame_27 = cmds.text(l="By Frame:")
		byFrameField_27 = cmds.textField("byFrameField_27", en=False)
	
	if len(allShots) >= 28:
		checkBox_28 = cmds.checkBox("checkBox_28", l="", value=1)
		cameraName_28 = cmds.text("cameraName_28", l=cmds.shot(allShots[27], query=True, currentCamera = True))
		startFrame_28 = cmds.text(l="Start Frame:  ")
		startFrameField_28 = cmds.textField("startFrameField_28", it=int(cmds.shot(allShots[27], query=True, startTime = True)))
		endFrame_28 = cmds.text(l="End Frame:")
		endFrameField_28 = cmds.textField("endFrameField_28", it=int(cmds.shot(allShots[27], query=True, endTime = True)))
		byFrame_28 = cmds.text(l="By Frame:")
		byFrameField_28 = cmds.textField("byFrameField_28", en=False)
	
	if len(allShots) >= 29:
		checkBox_29 = cmds.checkBox("checkBox_29", l="", value=1)
		cameraName_29 = cmds.text("cameraName_29", l=cmds.shot(allShots[28], query=True, currentCamera = True))
		startFrame_29 = cmds.text(l="Start Frame:  ")
		startFrameField_29 = cmds.textField("startFrameField_29", it=int(cmds.shot(allShots[28], query=True, startTime = True)))
		endFrame_29 = cmds.text(l="End Frame:")
		endFrameField_29 = cmds.textField("endFrameField_29", it=int(cmds.shot(allShots[28], query=True, endTime = True)))
		byFrame_29 = cmds.text(l="By Frame:")
		byFrameField_29 = cmds.textField("byFrameField_29", en=False)
	
	if len(allShots) >= 30:
		checkBox_30 = cmds.checkBox("checkBox_30", l="", value=1)
		cameraName_30 = cmds.text("cameraName_30", l=cmds.shot(allShots[29], query=True, currentCamera = True))
		startFrame_30 = cmds.text(l="Start Frame:  ")
		startFrameField_30 = cmds.textField("startFrameField_30", it=int(cmds.shot(allShots[29], query=True, startTime = True)))
		endFrame_30 = cmds.text(l="End Frame:")
		endFrameField_30 = cmds.textField("endFrameField_30", it=int(cmds.shot(allShots[29], query=True, endTime = True)))
		byFrame_30 = cmds.text(l="By Frame:")
		byFrameField_30 = cmds.textField("byFrameField_30", en=False)
	
	if len(allShots) >= 31:
		checkBox_31 = cmds.checkBox("checkBox_31", l="", value=1)
		cameraName_31 = cmds.text("cameraName_31", l=cmds.shot(allShots[30], query=True, currentCamera = True))
		startFrame_31 = cmds.text(l="Start Frame:  ")
		startFrameField_31 = cmds.textField("startFrameField_31", it=int(cmds.shot(allShots[30], query=True, startTime = True)))
		endFrame_31 = cmds.text(l="End Frame:")
		endFrameField_31 = cmds.textField("endFrameField_31", it=int(cmds.shot(allShots[30], query=True, endTime = True)))
		byFrame_31 = cmds.text(l="By Frame:")
		byFrameField_31 = cmds.textField("byFrameField_31", en=False)
	
	if len(allShots) >= 32:
		checkBox_32 = cmds.checkBox("checkBox_32", l="", value=1)
		cameraName_32 = cmds.text("cameraName_32", l=cmds.shot(allShots[31], query=True, currentCamera = True))
		startFrame_32 = cmds.text(l="Start Frame:  ")
		startFrameField_32 = cmds.textField("startFrameField_32", it=int(cmds.shot(allShots[31], query=True, startTime = True)))
		endFrame_32 = cmds.text(l="End Frame:")
		endFrameField_32 = cmds.textField("endFrameField_32", it=int(cmds.shot(allShots[31], query=True, endTime = True)))
		byFrame_32 = cmds.text(l="By Frame:")
		byFrameField_32 = cmds.textField("byFrameField_32", en=False)
	
	if len(allShots) >= 33:
		checkBox_33 = cmds.checkBox("checkBox_33", l="", value=1)
		cameraName_33 = cmds.text("cameraName_33", l=cmds.shot(allShots[32], query=True, currentCamera = True))
		startFrame_33 = cmds.text(l="Start Frame:  ")
		startFrameField_33 = cmds.textField("startFrameField_33", it=int(cmds.shot(allShots[32], query=True, startTime = True)))
		endFrame_33 = cmds.text(l="End Frame:")
		endFrameField_33 = cmds.textField("endFrameField_33", it=int(cmds.shot(allShots[32], query=True, endTime = True)))
		byFrame_33 = cmds.text(l="By Frame:")
		byFrameField_33 = cmds.textField("byFrameField_33", en=False)
	
	if len(allShots) >= 34:
		checkBox_34 = cmds.checkBox("checkBox_34", l="", value=1)
		cameraName_34 = cmds.text("cameraName_34", l=cmds.shot(allShots[33], query=True, currentCamera = True))
		startFrame_34 = cmds.text(l="Start Frame:  ")
		startFrameField_34 = cmds.textField("startFrameField_34", it=int(cmds.shot(allShots[33], query=True, startTime = True)))
		endFrame_34 = cmds.text(l="End Frame:")
		endFrameField_34 = cmds.textField("endFrameField_34", it=int(cmds.shot(allShots[33], query=True, endTime = True)))
		byFrame_34 = cmds.text(l="By Frame:")
		byFrameField_34 = cmds.textField("byFrameField_34", en=False)
	
	if len(allShots) >= 35:
		checkBox_35 = cmds.checkBox("checkBox_35", l="", value=1)
		cameraName_35 = cmds.text("cameraName_35", l=cmds.shot(allShots[34], query=True, currentCamera = True))
		startFrame_35 = cmds.text(l="Start Frame:  ")
		startFrameField_35 = cmds.textField("startFrameField_35", it=int(cmds.shot(allShots[34], query=True, startTime = True)))
		endFrame_35 = cmds.text(l="End Frame:")
		endFrameField_35 = cmds.textField("endFrameField_35", it=int(cmds.shot(allShots[34], query=True, endTime = True)))
		byFrame_35 = cmds.text(l="By Frame:")
		byFrameField_35 = cmds.textField("byFrameField_35", en=False)
	
	if len(allShots) >= 36:
		checkBox_36 = cmds.checkBox("checkBox_36", l="", value=1)
		cameraName_36 = cmds.text("cameraName_36", l=cmds.shot(allShots[35], query=True, currentCamera = True))
		startFrame_36 = cmds.text(l="Start Frame:  ")
		startFrameField_36 = cmds.textField("startFrameField_36", it=int(cmds.shot(allShots[35], query=True, startTime = True)))
		endFrame_36 = cmds.text(l="End Frame:")
		endFrameField_36 = cmds.textField("endFrameField_36", it=int(cmds.shot(allShots[35], query=True, endTime = True)))
		byFrame_36 = cmds.text(l="By Frame:")
		byFrameField_36 = cmds.textField("byFrameField_36", en=False)
	
	if len(allShots) >= 37:
		checkBox_37 = cmds.checkBox("checkBox_37", l="", value=1)
		cameraName_37 = cmds.text("cameraName_37", l=cmds.shot(allShots[36], query=True, currentCamera = True))
		startFrame_37 = cmds.text(l="Start Frame:  ")
		startFrameField_37 = cmds.textField("startFrameField_37", it=int(cmds.shot(allShots[36], query=True, startTime = True)))
		endFrame_37 = cmds.text(l="End Frame:")
		endFrameField_37 = cmds.textField("endFrameField_37", it=int(cmds.shot(allShots[36], query=True, endTime = True)))
		byFrame_37 = cmds.text(l="By Frame:")
		byFrameField_37 = cmds.textField("byFrameField_37", en=False)
	
	if len(allShots) >= 38:
		checkBox_38 = cmds.checkBox("checkBox_38", l="", value=1)
		cameraName_38 = cmds.text("cameraName_38", l=cmds.shot(allShots[37], query=True, currentCamera = True))
		startFrame_38 = cmds.text(l="Start Frame:  ")
		startFrameField_38 = cmds.textField("startFrameField_38", it=int(cmds.shot(allShots[37], query=True, startTime = True)))
		endFrame_38 = cmds.text(l="End Frame:")
		endFrameField_38 = cmds.textField("endFrameField_38", it=int(cmds.shot(allShots[37], query=True, endTime = True)))
		byFrame_38 = cmds.text(l="By Frame:")
		byFrameField_38 = cmds.textField("byFrameField_38", en=False)
	
	if len(allShots) >= 39:
		checkBox_39 = cmds.checkBox("checkBox_39", l="", value=1)
		cameraName_39 = cmds.text("cameraName_39", l=cmds.shot(allShots[38], query=True, currentCamera = True))
		startFrame_39 = cmds.text(l="Start Frame:  ")
		startFrameField_39 = cmds.textField("startFrameField_39", it=int(cmds.shot(allShots[38], query=True, startTime = True)))
		endFrame_39 = cmds.text(l="End Frame:")
		endFrameField_39 = cmds.textField("endFrameField_39", it=int(cmds.shot(allShots[38], query=True, endTime = True)))
		byFrame_39 = cmds.text(l="By Frame:")
		byFrameField_39 = cmds.textField("byFrameField_39", en=False)
	
	if len(allShots) >= 40:
		checkBox_40 = cmds.checkBox("checkBox_40", l="", value=1)
		cameraName_40 = cmds.text("cameraName_40", l=cmds.shot(allShots[39], query=True, currentCamera = True))
		startFrame_40 = cmds.text(l="Start Frame:  ")
		startFrameField_40 = cmds.textField("startFrameField_40", it=int(cmds.shot(allShots[39], query=True, startTime = True)))
		endFrame_40 = cmds.text(l="End Frame:")
		endFrameField_40 = cmds.textField("endFrameField_40", it=int(cmds.shot(allShots[39], query=True, endTime = True)))
		byFrame_40 = cmds.text(l="By Frame:")
		byFrameField_40 = cmds.textField("byFrameField_40", en=False)
	
	# replace end frame with start frame if camera keyframes have same value
	for i in range(1, len(allShots) + 1):
		print "End frame [", cmds.textField("endFrameField_" + str(i), tx=True, query=True), "] for camera [", cmds.text("cameraName_" + str(i), query=True, l=True), "] got set to start frame [", cmds.textField("startFrameField_" + str(i), tx=True, query=True), "] (no difference between keys detected)"
    		if cmds.keyframe(cmds.text("cameraName_" + str(i), query=True, l=True), time=(int(cmds.textField("startFrameField_" + str(i), tx=True, query=True)), int(cmds.textField("startFrameField_" + str(i), tx=True, query=True))), query=True, eval=True) == cmds.keyframe(cmds.text("cameraName_" + str(i), query=True, l=True), time=(int(cmds.textField("endFrameField_" + str(i), tx=True, query=True)), int(cmds.textField("endFrameField_" + str(i), tx=True, query=True))), query=True, eval=True):
    			cmds.textField("endFrameField_" + str(i), tx=cmds.textField("startFrameField_" + str(i), tx=True, query=True), edit=True, bgc=[0.5, 0.85, 0])
	
	
	cmds.setParent("..")
	cmds.separator(h=10, st='in')
	
	cmds.intSliderGrp("vertexMargin", l="Vertex margin: ", v=0, cw3=[105,40,200], min=0, max=5, fmx=50, f=True)
	cmds.separator(h=10, st='in')
	
	cmds.rowColumnLayout(nc=2)
	cmds.button("floodButton", l="Flood base object vertices with a colour", w=315, al="center", c=floodButton)
	cmds.button("rampAttr", l="Select ramp attributes", w=315, al="center", c=selectColourRamp)
	cmds.setParent("..")
	cmds.separator(h=10, st='in')
	
	global rampPresets
	rampPresets = cmds.optionMenu( label='Ramp Preset:    ', changeCommand=rampPresetChange)
	cmds.menuItem( label='Custom')
	cmds.menuItem( label='Zbrush Remesh')
	cmds.menuItem( label='Heat Map')
	
	cmds.rampColorPort( node=colourRamp, width=372, height = 125)
	
	cmds.separator(h=10, st='in')
	
	# paint button
	cmds.rowColumnLayout(nc=2)
	cmds.button("paintButton", l="Start Painting", w=315, h = 40, al="center", c=executeButton)
	cmds.button("exportVtxMap", en=False, l="Export vertex colour map", w=315, h = 40, al="center", c=vtxMapButton)
	cmds.setParent("..")

	
	# reset button
	cmds.button("resetButton", l="Reset to default values", w=370, al="center", c=windowUI)
	
	cmds.separator(h=10, st='in')
	
	cmds.text("Yet to implement: byFrame functionality",ww=True, fn="smallPlainLabelFont")
	
	cmds.showWindow("windowUI")
	
windowUI()
