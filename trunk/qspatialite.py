"""
/***************************************************************************
 QspatiaLite
                                 A QGIS plugin inspired by "CustomDBquery" and "SpatiaLite_manager" plugins
 SpatiaLite GUI for SpatiaLite
                              -------------------
        begin                : 2011-03-15
        copyright            : (C) 2011 by riviere
        email                : romain.riviere.974@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from qgis.core import *
# Initialize Qt resources from file resources.py
import resources
# Import the code for the dialog
from qspatialitedialog import QspatiaLiteDialog

class QspatiaLite:

    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface
	self.mlr = QgsMapLayerRegistry.instance()

    def initGui(self):
        # Create action that will start plugin configuration
        self.action = QAction(QIcon(":/plugins/qspatialite/icon.png"), \
            "QspatiaLite", self.iface.mainWindow())
        # connect the action to the run method
        QObject.connect(self.action, SIGNAL("triggered()"), self.run)

        # Add toolbar button and menu item
        self.iface.addToolBarIcon(self.action)
        #self.iface.addPluginToMenu("&QspatiaLite", self.action)
	#add to Database menu
	if hasattr(self.iface, "addPluginToDatabaseMenu"):
	    self.iface.addPluginToDatabaseMenu("&SpatiaLite", self.action)
	else:
	    self.iface.addPluginToMenu("&SpatiaLite", self.action)

    def unload(self):
        # Remove the plugin menu item and icon
        #self.iface.removePluginMenu("&QspatiaLite",self.action)
	#remove from Database menu
	if hasattr(self.iface, "removePluginDatabaseMenu"):
	    self.iface.removePluginDatabaseMenu("&SpatiaLite", self.action)
	else:
	    self.iface.removePluginMenu("&SpatiaLite", self.action)
        self.iface.removeToolBarIcon(self.action)

    # run method that performs all the real work
    def run(self):
        # create and show the dialog
        dlg = QspatiaLiteDialog(self.load_to_canvas,self.get_layer_names,self.save_layer,self.delete_tmpshp, self.import_gis_files, self.viewresult, self.export2ogr, self.iface.mainWindow())
        # show the dialog
        dlg.show()
        result = dlg.exec_()
        # See if OK was pressed
        if result == 1:
            # do something useful (delete the line containing pass and
            # substitute with your code
            pass

#Load query result-set to QGIS Canvas
    def load_to_canvas(self, query, provider, connectionSettings, geomField,
                       idField, newTableName=None, dbSchema=None):
        if newTableName is None:
            newTableName = 'sqlLayer'
        print("load_to_canvas method called")
        if provider == 'spatialite':
            uri = self.prepare_spatialite_uri(connectionSettings, query,
                                              geomField, idField)
        #print("uri: %s" % uri.uri())
        newLayer = QgsVectorLayer(uri.uri(), newTableName, provider.lower())
        if newLayer.isValid():
            self.mlr.addMapLayer(newLayer)
        else:
            print("Invalid layer")
            text = """Your query couldn't be parsed as a valid layer. Remember to 
alias your columns according to the names asked in the 'Geometry column' and 'Identifier column' fields."""
            QMessageBox.warning(None, 'Invalid layer', text)

    def prepare_spatialite_uri(self, connectionSettings, query, 
                              geomField, idField):
        uri = QgsDataSourceURI()
        uri.setDatabase(connectionSettings["sqlitepath"])
	#print "%s" % query
        uri.setDataSource('', "%s" % query, geomField, '', idField)
        return uri

# Return list of names of all layers in QgsMapLayerRegistry
    def get_layer_names(self):
	layermap = QgsMapLayerRegistry.instance().mapLayers()
	layerlist = []
	for name, layer in layermap.iteritems():
		if layer.type() == QgsMapLayer.VectorLayer:
			layerlist.append( unicode( layer.name() ) )
	return layerlist

    def save_layer(self, layer, table_name, charset, srid, selected=False, virtualshp=False, batch=False):
	#use virtual shape
	if virtualshp==True:
		# make sure layer doesn't already exist
	      	self.delete_tmpshp()
		# create new layer
		Qlayer=self.getVectorLayerByName( layer )
		# recently added: avoid pkuid field pb while importing to spatialite
		dataP=Qlayer.dataProvider()
		fldIdx = dataP.fieldNameIndex("pkuid")
		if fldIdx != -1:
			print "Field PKUID will be removed automaticaly!"
			Qlayer.startEditing()
			Qlayer.deleteAttribute(fldIdx)
		#end......................................................................................................
		Qsrid = QgsCoordinateReferenceSystem()
		Qsrid.createFromEpsg(srid)
		if not Qsrid.isValid(): #check if crs is ok
			return False
		if selected==True and Qlayer.selectedFeatureCount()==0:
			return "ok"
		error= QgsVectorFileWriter.writeAsShapefile(Qlayer, "shape_export.shp", charset, Qsrid, selected)
		if error == QgsVectorFileWriter.NoError:
			return True
		else:
			return False

	#use direct export:
	#get layer by its name
	if batch==True: # used for saving layers not in qgis canvas
		vlayer=layer	
	else:
		vlayer=self.getVectorLayerByName( layer )
	table_name=unicode(table_name).encode('utf-8').replace('"',"'") #avoid " in layer name
	#new srid
	Qsrid = QgsCoordinateReferenceSystem()
	Qsrid.createFromEpsg(srid)
	if not Qsrid.isValid(): #check if crs is ok
		return False,'srid'
	vlayer.setCrs(Qsrid)

	#retrieve geometry type
	geom=['MULTIPOINT','MULTILINESTRING','MULTIPOLYGON','UnknownGeometry']
	geometry=geom[vlayer.geometryType()]
	#get selected values 
	select_ids=[]
	if selected==True:
		if vlayer.selectedFeatureCount()==0:
			print 'No data selected'
			return False,False
		select_ids=vlayer.selectedFeaturesIds()

	#data provider encoding
	vlayer.setProviderEncoding(charset)
	provider = vlayer.dataProvider()

	fld_names = [name.name() for id,name in provider.fields().iteritems()]  #list with fields names
	fld_names2=[unicode(name).encode('utf-8').replace("'"," ").replace('"'," ") for name in fld_names]  # string list for field name  #avoid ' and " in fields names
	# 1/ decode string 2/and encode in utf-8

	feat = QgsFeature()
	allAttrs = provider.attributeIndexes()

	# start data retreival: fetch geometry and all attributes for each feature //except PKUID eventually
	fldDesc = provider.fieldNameIndex("pkuid")
	if fldDesc != -1:
		print "Pkuid already exists and will be replaced!"
		del allAttrs[fldDesc] #remove pkuid Field
		del fld_names2[fldDesc] #remove pkuid Field

	#select every fields except pkuid
	provider.select(allAttrs)

	#prepare list of SQL and parameters
	SQL=[]
	params=[]
	#Create table with all fields:
	fields='","'.join(fld_names2)
	SQL.append("""CREATE TABLE "%s" (PKUID INTEGER PRIMARY KEY AUTOINCREMENT, Geometry,"%s")"""%(table_name,fields))
	params.append(())
	SQL.append("SELECT RecoverGeometryColumn(?,'Geometry',?,?,2)")
	params.append((table_name,srid,geometry,))

	# retreive every feature with its geometry and attributes
	while provider.nextFeature(feat):
		# selected features:
		if selected==True and feat.id()not in select_ids:
			continue 
		# fetch geometry
		geom = feat.geometry()
		#WKB=geom.asWkb()
		WKT=geom.exportToWkt()

		#prepare SQL Query: PKUID and GEOMETRY
		values_auto=['NULL','CastToMulti(GeomFromText("%s",%s))'%(WKT,srid)]
		# fetch map of attributes
		attrs = feat.attributeMap()

		# attrs is a dictionary: key = field index, value = QgsFeatureAttribute
		# show all attributes and their values
		values_perso=[]
		for (k,attr) in attrs.iteritems():
			values_perso.append(attr.toString())
		#Finish SQL query
		SQL.append("""INSERT INTO "%s" VALUES (%s,%s)"""%(table_name,','.join([unicode(value).encode('utf-8') for value in values_auto]),','.join('?'*len(values_perso))))
		params.append(tuple([unicode(value) for value in values_perso]))
	#Just a quick check:
	if len(SQL)!=len(params):
		return False,1
	# we now have a list of SQl query to execute in QSpatiaLite
	return SQL,params

    def delete_tmpshp(self):
      	QgsVectorFileWriter.deleteShapeFile("shape_export.shp")


# Return QgsVectorLayer from a layer name ( as string )
    def getVectorLayerByName( self, myName ):
	layermap = QgsMapLayerRegistry.instance().mapLayers()
	for name, layer in layermap.iteritems():
		if layer.type() == QgsMapLayer.VectorLayer and layer.name() == myName:
			if layer.isValid():
				return layer
			else:
				return None
	return None


    def import_gis_files(self, fileNames, srid, charset):
	SQL_List=[]
	params_List=[]	#avoir same names for layers:
	names=[]
	#Upload each File
	for fileName in fileNames:
		SQL=[]
		name = unicode(QFileInfo(fileName).baseName()) # get file name, without extension = default layer name
		#avoir same names for layers: (non casse sensitive)
		if name.upper() in names:
			print u'Layer name -%s- already exists. Will be rename %s_2'%(name,name)
			name=u'%s_2'%name
		names.append(name.upper())

		layer = QgsVectorLayer(fileName, name, "ogr") #Load layer in qgis
		if not layer.isValid():
			QMessageBox.warning(None, 'Layer failed to load in QGIS', "Layer:\n%s\nFailed to Load in QGIS and will not be uploaded to SpatiaLite DB"%fileName)
			continue
		#charset=layer.dataProvider().encoding() #get layer encoding #not working...Qgis doesn't recognize the charset and set utf8....
		#if srid is None:
		#	srid=int(layer.crs().postgisSrid())

		SQL,params=self.save_layer(layer, name, charset, srid, batch=True)  #return list of SQl Statements  
		SQL_List.append(SQL)
		params_List.append(params)
	return SQL_List,params_List

    def viewresult(self,cols,cols_type,attr_data,geom_data,geometry,srid):
	from types import StringType, NoneType, IntType, BooleanType
	# A layer with the same name already exist?
	name="ResultSetView"
	while self.getVectorLayerByName(name) is not None:
		name+="_2"
	#Format geometry: ( avoid unix bug )
	geometry=geometry.lower()
	if geometry=="point":
		geometry='Point'
	elif geometry=='polygon':
		geometry='Polygon'
	elif geometry=='linestring':
		geometry='LineString'
	elif geometry=='multipoint':
		geometry='MultiPoint'
	elif geometry=='multilinestring':
		geometry='MultiLineString'
	elif geometry=='multipolygon':
		geometry='MultiPolygon'
	# create temporary layer
	vl = QgsVectorLayer(geometry, name, "memory")
	if not vl.isValid():
		#raise IOError, 'Impossible to create a memory layer in QGIS'
		QMessageBox.warning(None, "Operation cancelled", 'Impossible to create a memory layer in QGIS')
		return
	pr = vl.dataProvider()

	# add fields
	attrs=[]
	for i in range(0,len(cols)):
		if cols_type[i] in (StringType,NoneType):
			attr=QgsField(cols[i], QVariant.String)
		elif cols_type[i] in (IntType,BooleanType):
			attr=QgsField(cols[i], QVariant.Int)
		else:
			attr=QgsField(cols[i], QVariant.Double)
		attrs.append(attr)

	pr.addAttributes( attrs )
	vl.updateFieldMap() 
	features=[]
	for i in range(0,len(geom_data)):
		# add a feature
		fet = QgsFeature()
		fet.setGeometryAndOwnership(geom_data[i],len(geom_data[i])) #set geometry from wkb
		attr_map=dict() #attribute map dictionnary
		row=attr_data[i]
		for j in range(0,len(cols)): # create attribute map for current geometry
			attr_map[j]=QVariant(row[j])
		fet.setAttributeMap( attr_map )
		features.append(fet)
	pr.addFeatures( features )
	# update layer's extent when new features have been added
	# because change of extent in provider is not propagated to the layer
	try:
		vl.updateExtents()
	except:
		print 'Old QGIS API version'
	
	if srid is not None: #user choose a custom srid
		Qsrid = QgsCoordinateReferenceSystem()
		Qsrid.createFromEpsg(srid)
		vl.setCrs(Qsrid)

	# add layer to the registry
	QgsMapLayerRegistry.instance().addMapLayer(vl)

    def export2ogr(self,tables,geocols,connectionSettings,format,folder,charset,srids=None): #export tables to ogr layer format
	import os
	errors=[] #Store errors
	i=0
	for table in tables:
		#prepare uri
		uri = self.prepare_spatialite_uri(connectionSettings, table, geocols[i], 'ROWID')
		#check SRID
		srid=int(srids[i])
		Qsrid =QgsCoordinateReferenceSystem()
		Qsrid.createFromEpsg(srid)
		i+=1
		if not Qsrid.isValid():
			errors.append([table,"SRID (%s) not Valid"%srid])
			continue
		#create QGIS LAyer
        	layer = QgsVectorLayer(uri.uri(), table, 'spatialite')
        	if not layer.isValid():
			errors.append([table,"Can't load layer in QGIS"])
			continue
		#Write vector File
		os.chdir(r'%s'%folder)
            	error= QgsVectorFileWriter.writeAsVectorFormat(layer, table, charset, Qsrid, format)
		if not error == QgsVectorFileWriter.NoError:
			errors.append([table,"Can't save layer"])
			continue
			
	return errors
	
