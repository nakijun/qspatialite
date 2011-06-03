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
        dlg = QspatiaLiteDialog(self.load_to_canvas,self.get_layer_names,self.save_layer,self.delete_tmpshp, self.import_gis_files, self.iface.mainWindow())
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
	table_name=unicode(table_name).encode('utf-8')
	#new srid
	Qsrid = QgsCoordinateReferenceSystem()
	Qsrid.createFromEpsg(srid)
	vlayer.setCrs(Qsrid)

	#retrieve geometry type
	geom=['MULTIPOINT','MULTILINESTRING','MULTIPOLYGON','UnknownGeometry']
	geometry=geom[vlayer.geometryType()]
	#get selected values 
	select_ids=[]
	if selected==True:
		if vlayer.selectedFeatureCount()==0:
			print 'No data selected'
			return False
		select_ids=vlayer.selectedFeaturesIds()

	#data provider encoding
	vlayer.setProviderEncoding(charset)
	provider = vlayer.dataProvider()
	charset=str(charset)

	fld_names = [name.name() for id,name in provider.fields().iteritems()]  #list with fields names
	fld_names2=[unicode(name).encode('utf-8') for name in fld_names]  # string list for field name
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

	#prepare list of SQL Statements
	SQL=[]
	#Create table with all fields:
	fields="','".join(fld_names2)
	SQL.append('CREATE TABLE %s (PKUID INTEGER PRIMARY KEY AUTOINCREMENT, Geometry,%s)'%(table_name,"'"+fields+"'"))
	SQL.append("SELECT RecoverGeometryColumn('%s','Geometry',%s,'%s',2)"%(table_name,srid,geometry))

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
		values=['NULL','CastToMulti(GeomFromText("%s",%s))'%(WKT,srid)]
		# fetch map of attributes
		attrs = feat.attributeMap()

		# attrs is a dictionary: key = field index, value = QgsFeatureAttribute
		# show all attributes and their values
		for (k,attr) in attrs.iteritems():
			values.append("'"+attr.toString()+"'")

		#Finish SQL query
		values=','.join([unicode(value).encode('utf-8') for value in values])
		SQL.append('INSERT INTO %s VALUES (%s)'%(table_name, values))

	# we now have a list of SQl query to execute in QSpatiaLite
	return SQL

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


    def import_gis_files(self, fileNames, srid=None):
	SQL_List=[]
	#avoir same names for layers:
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
		charset=layer.dataProvider().encoding() #get layer encoding
		if srid is None:
			srid=int(layer.crs().postgisSrid())

		SQL=self.save_layer(layer, name, charset, srid, batch=True)  #return list of SQl Statements
		SQL_List.append(SQL)
	return SQL_List
