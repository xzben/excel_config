#encoding=utf-8
'''
Copyright 2016 YANG Huan (sy.yanghuan@gmail.com)

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
'''
from enum import Flag
import sys        

if sys.version_info < (3, 0):
  print('python version need more than 3.x')
  sys.exit(1)
    
import os
import string
import collections
import codecs
import getopt
import re
import json
import xml.etree.ElementTree as ElementTree
import xml.dom.minidom as minidom
import xlrd

def fillvalue(parent, name, value, isschema):
  if isinstance(parent, list):
    parent.append(value) 
  else:
    if isschema and not re.match('^_|[a-zA-Z]\w*$', name):
      raise ValueError('%s is a illegal identifier' % name)
    parent[name] = value
    
def getindex(infos, name):
  for index, item in enumerate(infos):
    if item == name:
      return index;
  return -1

def getscemainfo(typename, description):
  if isinstance(typename, BindType):
    typename = typename.typename
  return [typename, description] if description else [typename]
        
def getexportmark(sheetName):
  p = re.search('\|[' + string.whitespace + ']*(_|[a-zA-Z]\w+)', sheetName)
  return p.group(1) if p else False

def getIsMap(sheetName):
  p = re.search('\|['+string.whitespace+']*(map)(\d*)+['+string.whitespace+']*\|*', sheetName)
  return p.group(1) == "map" if p else False

def getMapLevel(sheetName):
  p = re.search('\|['+string.whitespace+']*map([0-9])+['+string.whitespace+']*\|*', sheetName)
  level = 1
  if p :
    level = p.group(1)
  return int(level);

def issignmatch(signarg, sign):
  if signarg is None:
    return True
  return True if [s for s in re.split(r'[/\\, :]', sign) if s in signarg] else False

def isoutofdate(srcfile, tarfile):
  return True;
  # return not os.path.isfile(tarfile) or os.path.getmtime(srcfile) > os.path.getmtime(tarfile)

def gerexportfilename(root, format_, folder):
  filename = root +  '.' + format_
  return os.path.join(folder, filename)

def splitspace(s):
  return re.split(r'[' + string.whitespace + ']+', s.strip())

def buildbasexml(parent, name, value):
  value = str(value)
  if parent.tag == name + 's':
    element = ElementTree.Element(name)
    element.text = value
    parent.append(element)
  else:
    parent.set(name, value)    
            
def buildlistxml(parent, name, list_):
  element = ElementTree.Element(name)
  parent.append(element)
  for v in list_:
    buildxml(element, name[:-1], v)    

def buildobjxml(parent, name, obj):
  element = ElementTree.Element(name)
  parent.append(element)
  
  for k, v in obj.items():
    buildxml(element, k, v)
        
def buildxml(parent, name, value):
  if isinstance(value, int) or isinstance(value, float) or isinstance(value, str):
    buildbasexml(parent, name, value)
      
  elif isinstance(value, list):
    buildlistxml(parent, name, value)
      
  elif isinstance(value, dict):
    buildobjxml(parent, name, value)
            
def savexml(record):
  book = ElementTree.ElementTree()
  book.append = lambda e: book._setroot(e)
  buildxml(book, record.root, record.obj)
  
  xmlstr = ElementTree.tostring(book.getroot(), 'utf-8')
  dom = minidom.parseString(xmlstr)
  with codecs.open(record.exportfile, 'w', 'utf-8') as f:
    dom.writexml(f, '', '  ', '\n', 'utf-8')
      
  print('save %s from %s in %s' % (record.exportfile, record.sheet.name, record.path))
  
def newline(count):
  return '\n' + '  ' * count
  
def tolua(obj, indent = 1):    
  if isinstance(obj, int) or isinstance(obj, float) or isinstance(obj, str):
    yield json.dumps(obj, ensure_ascii = False)
  else:
    yield '{'
    islist = isinstance(obj, list)
    isfirst = True
    for i in obj:
      if isfirst:
        isfirst = False
      else:
        yield ','
      yield newline(indent)
      if not islist:
        k = i
        i = obj[k]
        keyname = ""
        if isinstance(k, str):
          keyname = str(k)
        else:
          keyname = '[' +str(k) + ']'

        yield keyname 
        yield ' = '                
      for part in tolua(i, indent + 1):
        yield part
    yield newline(indent - 1)
    yield '}'
    
def toycl(obj, indent = 0):
  islist = isinstance(obj, list)
  for i in obj:
    yield newline(indent)  
    if not islist:
      k = i
      i = obj[k]
      yield k 
    if isinstance(i, int) or isinstance(i, float) or isinstance(i, str): 
      if not islist:
        yield ' = '
      yield json.dumps(i, ensure_ascii = False)
    else:
      if not islist:
        yield ' '
      yield '{'
      for part in toycl(i, indent + 1):
        yield part
      yield newline(indent)  
      yield '}'     


def cell_real_value(row, col, sheet):
  for merged in sheet.merged_cells:
    if (row <= merged[0] and row < merged[1] and col >= merged[2] and col < merged[3]):
      return sheet.cell_value(merged[0], merged[2]);
  return sheet.cell_value(row, col)

def cell_size(row, col, sheet):
  for merged in sheet.merged_cells:
    if (row >= merged[0] and row < merged[1] and col >= merged[2] and col < merged[3]):
      return (merged[1] - merged[0], merged[3] - merged[2])
  return (1, 1)

def get_type_value(typename, value):
  if typename == 'int':
    value = int(float(value))
  elif typename == 'double':
    value = float(value)   
  elif typename == 'string':
    if value.endswith('.0'):          # may read is like "123.0"
      try:
        value = str(int(float(value)))
      except ValueError:
        value = str(value)
    else:            
      value = str(value)
  elif typename == 'bool':
    try:
      value = int(float(value))
      value = False if value == 0 else True 
    except ValueError:
      value = value.lower() 
      if value in ('false', 'no', 'off'):
        value = False
      elif value in ('true', 'yes', 'on'):
        value = True
      else:    
        raise ValueError('%s is a illegal bool value' % value)

  return str(value) 

def get_obj_str_value(obj, type_):
  fieldname = type_.strip('{}[]')
  if fieldname == '':
    return ''
  fieldnamestypes = fieldname.split(':')
  retvalue = ""
  for i in range(0, len(fieldnamestypes)):
    fieldtype, fieldname = splitspace(fieldnamestypes[i])
    fieldValue = ""
    if fieldname in obj.keys():
      fieldValue = get_type_value(fieldtype, obj[fieldname])
    if retvalue != "":
      retvalue = retvalue + ":"
    retvalue = retvalue + fieldValue

  return retvalue    

def get_obj_type_first_field(type_):
  fieldnamestypes = type_.strip('{}').split(':')
  fieldtype, fieldname = splitspace(fieldnamestypes[0])
  return fieldname

def exportexcel(context):
  Exporter(context).export()
  print("export finsish successful!!!")
    
class BindType:
  def __init__(self, type_):
    self.typename = type_
      
  def __eq__(self, other):
    return self.typename == other
    
class Record:
  def __init__(self, path, sheet, exportfile, root, item, obj, exportmark):
    self.path = path 
    self.sheet = sheet 
    self.exportfile = exportfile 
    self.root = root 
    self.item = item
    self.setobj(obj)
    self.exportmark = exportmark

  def setobj(self, obj):    
    self.schema = obj[0] if obj else None
    self.obj = obj[1] if obj else None
        
class Constraint:
  def __init__(self, mark, filed):
    self.mark = mark
    self.field = filed     
        
class Exporter:
  configsheettitles = ('name', 'value', 'type', 'sign', 'description')
  spacemaxrowcount = 3
  
  def __init__(self, context):
    self.context = context
    self.records = []
    self.constraints = []
  
  def gettype(self, type_):
    if type_[-2] == '[' and  type_[-1] == ']':
      return 'list'
    if type_[0] == '{' and type_[-1] == '}':
      return 'obj'
    if type_ in ('int', 'double', 'string', 'bool', 'map'):
      return type_
    
    p = re.search('(int|string)[' + string.whitespace + ']*\((\w+)\.(\w+)\.*(\w*)\)', type_)
    if p:
      type_ = BindType(p.group(1))
      type_.mark = p.group(2)
      if p.group(4) == "":
        type_.field1 = None
        type_.field = p.group(3)
      else:
        type_.field1 = p.group(3)
        type_.field = p.group(4)
      
      return type_
        
    raise ValueError('%s is not a legal type' % type_)
    
  def buildlistexpress(self, parent, type_, name, value, isschema):
    basetype = type_[:-2]        
    list_ = []
    if isschema:
      self.buildexpress(list_, basetype, name, None, isschema)
      list_ = getscemainfo(list_[0], value)
    else:
      value = value.strip('[]')
      if basetype == 'string' and '\,' in value:
        valuelist = value.replace('\,', '\0').split(',')
        valuelist = [s.replace('\0', ',') for s in valuelist]
      else:
        valuelist = value.split(',')
      for v in valuelist:
        self.buildexpress(list_, basetype, name, v)
       
    fillvalue(parent, name + 's', list_, isschema)     
      
  def buildobjexpress(self, parent, type_, name, value, isschema):
    obj = collections.OrderedDict()
    fieldnamestypes = type_.strip('{}').split(':')
    
    if isschema:
      for i in range(0, len(fieldnamestypes)):
        fieldtype, fieldname = splitspace(fieldnamestypes[i])
        self.buildexpress(obj, fieldtype, fieldname, None, isschema)
      obj = getscemainfo(obj, value)
    else:
      fieldValues = value.strip('{}').split(':')
      for i in range(0, len(fieldnamestypes)):
        if i < len(fieldValues):
          fieldtype, fieldname = splitspace(fieldnamestypes[i])
          self.buildexpress(obj, fieldtype, fieldname, fieldValues[i])

    fillvalue(parent, name, obj, isschema)       
      
  def buildbasexpress(self, parent, type_, name, value, isschema):
    typename = self.gettype(type_) 
    if isschema:
      value = getscemainfo(typename, value)
    else:
      if v.isspace() and typename != 'string':
        return
        
      if typename == 'int':
        value = int(float(value))
      elif typename == 'double':
        value = float(value)   
      elif typename == 'string':
        if value.endswith('.0'):          # may read is like "123.0"
          try:
            value = str(int(float(value)))
          except ValueError:
            value = str(value)
        else:            
          value = str(value)
      elif typename == 'bool':
        try:
          value = int(float(value))
          value = False if value == 0 else True 
        except ValueError:
          value = value.lower() 
          if value in ('false', 'no', 'off'):
            value = False
          elif value in ('true', 'yes', 'on'):
            value = True
          else:    
            raise ValueError('%s is a illegal bool value' % value) 
    fillvalue(parent, name, value, isschema)   
    
    if not isschema and isinstance(typename, BindType):
      self.addconstraint(typename.mark, typename.field, (type_, name, value), typename.field1)
        
  def buildexpress(self, parent, type_, name, value, isschema = False):
    typename = self.gettype(type_)
    if typename == 'list':
      self.buildlistexpress(parent, type_, name, value, isschema)
    elif typename == 'obj':
      self.buildobjexpress(parent, type_, name, value, isschema)
    else:
      self.buildbasexpress(parent, type_, name, value, isschema)
      
  def getrootname(self, exportmark, isitem):
    return exportmark + 's' + (self.context.extension or '') if isitem else exportmark + (self.context.extension or '')

  def export(self):
    paths = re.split(r'[,;|]+', context.path.strip())

    for self.path in paths:
      if not self.path:
        continue
      
      self.checkpath(self.path)
      data = xlrd.open_workbook(self.path)
      cout = None
      for sheet in data.sheets():
        exportmark = getexportmark(sheet.name)
        self.sheetname = sheet.name
        if exportmark:
          coutmark = sheet.name.endswith('<<')
          coutendmark = sheet.name.endswith('>>')
          
          mapmark = getIsMap(sheet.name)
          maplevel = 1
          if mapmark:
            maplevel = getMapLevel(sheet.name)

          configtitleinfo = self.getconfigsheetfinfo(sheet)
          if not configtitleinfo:
            root = self.getrootname(exportmark, not coutmark)
            item = exportmark
          else:
            root = self.getrootname(exportmark, False)
            item = None
          
          if not cout:
            exportfile = gerexportfilename(root, self.context.format, self.context.folder)
            self.checksheetname(self.path, sheet.name, root)
        
            exportobj = None
            nochanged = False
            if isoutofdate(self.path, exportfile):
              if item:
                exportobj = self.exportitemsheet(sheet, mapmark, maplevel)
              else:
                exportobj = self.exportconfigsheet(sheet, configtitleinfo)
            else:
              nochanged = True
              print(exportfile + ' is not change, so skip!')

            if coutmark:
              if not item:
                cout = exportobj
              else:
                cout = (collections.OrderedDict(), collections.OrderedDict())
                cout[0][item + 's'] = [[exportobj[0]]]
                item = None
                exportobj = cout
                obj = exportobj[1]
                if obj:
                  cout[1][item + 's'] = obj
                  
            self.addrecord(self.path, sheet, exportfile, root, item, exportobj, exportmark)
            if coutmark and nochanged:
              break
          else:
            if item:
              exportobj = self.exportitemsheet(sheet, mapmark, maplevel)
              cout[0][item + 's'] = [[exportobj[0]]]
              obj = exportobj[1]
              if obj:
                cout[1][item + 's'] = obj
            else:
              exportobj = self.exportconfigsheet(sheet, configtitleinfo)
              cout[0].update(exportobj[0])   
              obj = exportobj[1]
              if obj:
                cout[1].update(obj)
          
          if coutendmark:
                cout = None;
                
    self.checkconstraint()
    self.saves()                
    
  def getconfigsheetfinfo(self, sheet):
    titles = sheet.row_values(0)
    
    nameindex = getindex(titles, self.configsheettitles[0])
    valueindex = getindex(titles, self.configsheettitles[1])
    typeindex = getindex(titles, self.configsheettitles[2])
    signindex = getindex(titles, self.configsheettitles[3])
    descriptionindex = getindex(titles, self.configsheettitles[4])
    
    if nameindex != -1 and valueindex != -1 and typeindex != -1:
      return (nameindex, valueindex, typeindex, signindex, descriptionindex)
    else:
      return None
        
  def exportitemsheet(self, sheet, isMap = False, mapLevel = 1 ):
    descriptions = sheet.row_values(0)
    types = sheet.row_values(1)
    names = sheet.row_values(2)
    signs = sheet.row_values(3)
    
    titleinfos = []
    schemaobj = collections.OrderedDict()
    
    try:
      for colindex in range(sheet.ncols):
        type_ = str(types[colindex]).strip()
        name = str(names[colindex]).strip()
        signmatch = issignmatch(self.context.sign, str(signs[colindex]).strip())
        titleinfos.append((type_, name, signmatch))
        
        if self.context.codegenerator:
          if type_ and name and signmatch:
            self.buildexpress(schemaobj, type_, name, descriptions[colindex], True)
                    
    except Exception as e: 
      e.args += ('%s has a title error, %s at %d column in %s' % (sheet.name, (type_, name), colindex + 1, self.path) , '')
      raise e
    
    obj = collections.OrderedDict()
    list_ = []
    hasexport = next((i for i in titleinfos if i[0] and i[1] and i[2]), False)
    if hasexport:
      try:
        spacerowcount = 0
        nextrow = 4
        for self.rowindex in range(4, sheet.nrows):
          if self.rowindex >= nextrow:
            row = sheet.row_values(self.rowindex)
            sizeInfo = cell_size(self.rowindex, 0, sheet)
            height = sizeInfo[0]
            nextrow = nextrow+height
            item = collections.OrderedDict()
            
            firsttext = str(row[0]).strip()
            if not firsttext:
              spacerowcount += 1
              if spacerowcount >= self.spacemaxrowcount:      # if space row is than max count, skil follow rows     
                break
            
            if not firsttext or firsttext[0] == '#':    # current line skip
              continue
              
            skiptokenindex = None   
            if firsttext[0] == '!':
              nextpos = firsttext.find('!', 1)
              if nextpos >= 2:
                signtoken = firsttext[1: nextpos]
                if issignmatch(self.context.sign, signtoken.strip()):
                  continue
                else:
                  skiptokenindex = len(signtoken) + 2
            
            itemkey = []

            nextcol = 0
            for self.colindex in range(sheet.ncols):
              if self.colindex >= nextcol: 
                curSizeInfo = cell_size(3, self.colindex, sheet)
                width = curSizeInfo[1]
                nextcol = nextcol + width
                value = ""
                signmatch = titleinfos[self.colindex][2]
                if signmatch:
                  type_ = titleinfos[self.colindex][0]
                  name = titleinfos[self.colindex][1]
                  typename = self.gettype(type_)
                  if width > 1 and typename == "list":
                    objData = collections.OrderedDict()
                    firstfieldkey = get_obj_type_first_field(type_).strip()
                    for curRow in range(self.rowindex, self.rowindex+height):
                      objkey = str(sheet.cell_value(curRow, self.colindex)).strip()
                      if objkey == firstfieldkey:
                        if firstfieldkey in objData.keys():
                            value = value + get_obj_str_value(objData, type_) + ","
                        objData = collections.OrderedDict()
                        
                      objvalue = str(sheet.cell_value(curRow, self.colindex+1)).strip()
                      objData[objkey] = objvalue
                    if firstfieldkey in objData.keys():
                      value = value + get_obj_str_value(objData, type_)

                  elif width > 1 and typename == "obj":
                    objData = collections.OrderedDict()
                    for curRow in range(self.rowindex, self.rowindex+height):
                      objkey = str(sheet.cell_value(curRow, self.colindex)).strip()
                      objvalue = str(sheet.cell_value(curRow, self.colindex+1)).strip()
                      objData[objkey] = objvalue
                    
                    value = get_obj_str_value(objData, type_)
                  elif width > 1 and typename == "map":
                    objData = collections.OrderedDict()
   
                  
                    for curRow in range(self.rowindex, self.rowindex+height):
                      objkey = str(sheet.cell_value(curRow, self.colindex)).strip()
                      objType = str(sheet.cell_value(curRow, self.colindex+1)).strip()
                      objvalue = str(sheet.cell_value(curRow, self.colindex+2)).strip()
                      if not (objkey == '' or objType == '' or objvalue == ''):
                        self.buildexpress(objData, objType, objkey, objvalue)
                    type_ = 'map'
                    value = objData
                  else:
                    value = str(row[self.colindex])

                  if skiptokenindex and self.colindex == 0:
                    value = value.lstrip()[skiptokenindex:]
                    
                  if type_ and name and value:
                    self.buildexpress(item, type_, name, value)

                  if len(itemkey) < mapLevel:
                    itemkey.append(item[name])

                spacerowcount = 0
                
            if isMap:
                if item:
                  setObj = obj
                  keyLen = len(itemkey)
                  for idx in range(0, keyLen-1):
                    key = itemkey[idx]
                    if not (key in setObj):
                      setObj[key] = collections.OrderedDict();
                    setObj = setObj[key]
                  
                  setObj[itemkey[keyLen-1]] = item
            else:
              if item:
                list_.append(item)
      except Exception as e:        
          e.args += ('%s has a error in %d row %d column in %s' % (sheet.name, self.rowindex + 1, self.colindex + 1, self.path) , '')
          raise e
    
    if isMap:
      return (schemaobj, obj)
    else:
      return (schemaobj, list_)
        
  def exportconfigsheet(self, sheet, titleindexs):
    nameindex = titleindexs[0]
    valueindex = titleindexs[1]
    typeindex = titleindexs[2]
    signindex = titleindexs[3]
    descriptionindex = titleindexs[4]
    
    schemaobj = collections.OrderedDict()
    obj = collections.OrderedDict()
    
    try:
      spacerowcount = 0
      self.colindex = 2
      
      for self.rowindex in range(1, sheet.nrows):
        row = sheet.row_values(self.rowindex) 
    
        name = str(row[nameindex]).strip()
        value = str(row[valueindex])
        type_ = str(row[typeindex]).strip()
        description = str(row[descriptionindex]).strip()
        
        if signindex > 0:
          sign = str(row[signindex]).strip()
          if not issignmatch(self.context.sign, sign):
            continue
          
        if not name and not value and not type_:
          spacerowcount += 1
          if spacerowcount >= self.spacemaxrowcount:
            break            # if space row is than max count, skil follow rows     
          continue
            
        if name and type_:
          if(name[0] != '#'):         # current line skip
            if self.context.codegenerator:
              self.buildexpress(schemaobj, type_, name, description, True)
            if value:    
              self.buildexpress(obj, type_, name, value)
          spacerowcount = 0    
              
    except Exception as e:
      e.args += ('%s has a error in %d row (%s, %s, %s) in %s' % (sheet.name, self.rowindex + 1, type_, name, value, self.path) , '')
      raise e
  
    return (schemaobj, obj)
    
  def saves(self):
    schemas = []
    for r in self.records:
        if r.obj:
          self.save(r)
          
          if self.context.codegenerator:        # has code generator
            schemas.append({ 'exportfile' : r.exportfile, 'root' : r.root, 'item' : r.item or r.exportmark, 'schema' : r.schema })
    
    if schemas and self.context.codegenerator:
      schemasjson = json.dumps(schemas, ensure_ascii = False, indent = 2)
      dir = os.path.dirname(self.context.codegenerator)
      if dir and not os.path.isdir(dir):
        os.makedirs(dir)
      with codecs.open(self.context.codegenerator, 'w', 'utf-8') as f:
        f.write(schemasjson)
                
  def save(self, record):
    if not record.obj:
      return
  
    if not os.path.isdir(self.context.folder):
      os.makedirs(self.context.folder)
        
    if self.context.format == 'json':
      jsonstr = json.dumps(record.obj, ensure_ascii = False, indent = 2)
      with codecs.open(record.exportfile, 'w', 'utf-8') as f:
        f.write(jsonstr)
      print('save %s from %s in %s' % (record.exportfile, record.sheet.name, record.path))
        
    elif self.context.format == 'xml':
      if record.item:
        record.obj = { record.item + 's' : record.obj }
      savexml(record) 
        
    elif self.context.format == 'lua':
      luastr = "".join(tolua(record.obj))
      with codecs.open(record.exportfile, 'w', 'utf-8') as f:
        f.write('return ')
        f.write(luastr)
      print('save %s from %s in %s' % (record.exportfile, record.sheet.name, record.path))
      
    elif self.context.format == 'ycl':
      g = toycl(record.obj)
      next(g) # skip first newline
      yclstr = "".join(g)
      with codecs.open(record.exportfile, 'w', 'utf-8') as f:
        f.write(yclstr)
      print('save %s from %s in %s' % (record.exportfile, record.sheet.name, record.path))

  def addrecord(self, path, sheet, exportfile, root, item, obj, exportmark):
    r = Record(path, sheet, exportfile, root, item, obj, exportmark)
    self.records.append(r)
      
  def checksheetname(self, path, sheetname, root):
    r = next((r for r in self.records if r.root == root), False)
    if r:
      raise ValueError('%s in %s is already defined in %s' % (root, path, r.path))
      
  def checkpath(self, path):
    r = next((r for r in self.records if r.path == path), False)
    if r:
      raise ValueError('%s is already export' % path)
            
  def addconstraint(self, mark, field, valueinfo, field1):
    c = Constraint(mark, field)
    c.field1 = field1
    c.valueinfo = valueinfo
    c.path = self.path
    c.sheetname = self.sheetname
    c.rowindex = self.rowindex
    c.colindex = self.colindex
    self.constraints.append(c)

  def checkconstraint(self):
    for c in self.constraints:
      r = None
      for record in self.records:
        if record.item == c.mark or record.exportmark == c.mark :
          if c.field1 != None:
            r = collections.OrderedDict()
            r.obj = record.obj[c.field1+"s"]
          else:
            r = record;
          break;
      if None == r:
        raise ValueError('%s(mark) not found ,%s has a constraint %s error in %d row %d column in %s' % (c.mark, c.sheetname, c.valueinfo, c.rowindex + 1, c.colindex + 1, c.path))
      
      if not r.obj:  # is not change so not load
        exportobj = self.exportitemsheet(r.sheet)
        r.setobj(exportobj)
      
      v = c.valueinfo[2]    
      find = False

      for ti in r.obj:
        if isinstance(ti, str) or isinstance(ti, int) or isinstance(ti, float):
          if(r.obj[ti][c.field] == v):
            find = True;
            break;
        elif isinstance(ti, object):
          if(ti[c.field] == v):
            find = True;
            break;
      # i = next((i for i in r.obj if r.obj[i][c.field] == v), False)    
      if not find:
        raise ValueError('%s(field) %s not found ,%s has a constraint %s error in %d row %d column in %s' % (c.field, v, c.sheetname, c.valueinfo, c.rowindex + 1, c.colindex + 1, c.path))
    
if __name__ == '__main__':
  class Context:
    '''usage python proton.py [-p filelist] [-f outfolder] [-e format]
    Arguments
    -p      : input excel files, use , or ; or space to separate
    -f      : out folder
    -e      : format, json or xml or lua or ycl

    Options
    -s      ：sign, controls whether the column is exported, defalut all export
    -t      : suffix, export file suffix
    -c      : a file path, save the excel structure to json
              the external program uses this file to automatically generate the read code
    -h      : print this help message and exit
    
    https://github.com/yanghuan/proton'''
  
  print('argv:' , sys.argv)
  opst, args = getopt.getopt(sys.argv[1:], 'p:f:e:s:t:c:h')

  context = Context()
  context.path = None
  context.folder = '.'
  context.format = 'json'
  context.sign = None
  context.extension = None
  context.codegenerator = None

  for op,v in opst:
    if op == '-p':
      context.path = v
    elif op == '-f':
      context.folder = v
    elif op == '-e':
      context.format = v.lower() 
    elif op == '-s':
      context.sign = v 
    elif op == '-t':
      context.extension = v
    elif op == '-c':
      context.codegenerator = v    
    elif op == '-h':
      print(Context.__doc__)
      sys.exit()
      
  if not context.path:
    print(Context.__doc__)
    sys.exit(2)
    
  exportexcel(context)