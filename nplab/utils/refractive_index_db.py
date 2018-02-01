import requests
import yaml
import os, inspect



class RefractiveIndexInfoDatabase(object):

	def __init__(self):
		#load library:
		dirpath =  os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
		library_path = os.path.normpath(dirpath+"/refractive_index_db_lib.yml")
		#print library_path
		with open(library_path,"r") as file:
			library = yaml.load(file.read())
			#loading library file from online location:
			# library_url = "https://raw.githubusercontent.com/imanyakin/refractiveindex.info-database/master/database/library.yml"
			# response = requests.get(library_url)
			# library = yaml.load(response._content)
			cls = self.__class__
			data = cls.get_data(library)
			data_dict = cls.make_dict(data)
			cls.test_converse_reversibility(data)
			dataset = cls.fetch_dataset_yaml(data[0])
			print cls.extract_refractive_indices(dataset)

	@classmethod
	def get_data(cls,it):
		'''
		Extract "data" labels from the library.yml file.
		Each item labelled as "data" is a path that can be accessed through internet
		:param it - iterable (list/dict) of the yaml file
		'''
		
		if type(it) == list:
			outp = []
			for i in it:
				outp = outp + cls.get_data(i)
			return outp
			# return [get_data(i) for i in it]
		elif type(it) == dict:
			outp = []
			if "content" in it.keys():
				outp = outp + cls.get_data(it["content"])
			if "data" in it.keys():
				outp = outp + [it["data"]]
		return outp

	@classmethod
	def make_dict(cls,data):
		'''
		Convert list of labels in A/B/C... format into a dictionary, tree nodes are either a list or a empty dictionary
		'''
		#set up output dict
		outp = dict()
		#leys
		keys = set([d.split("/")[0] for d in data])
		

		for k in keys:
			values = []
			for d in data:
				if k == d.split("/")[0]:
					value = "/".join(d.split("/")[1:])
					if len(value)>0:
						values.append(value)
			outp.update({k:RefractiveIndexInfoDatabase.make_dict(values)})

		#if all values of output dict are empty lists - collapse dict
		if all(len(v)==0 for v in outp.values()):
			return outp.keys()
		else:
			return outp

	@classmethod
	def make_data(cls,iterable):
		if type(iterable) == list:
			if len(iterable) > 0:
				return iterable
			else:
				return ''
		elif type(iterable) == dict:
			outp = []
			for k in iterable.keys():
				values = RefractiveIndexInfoDatabase.make_data(iterable[k])
				if len(values) > 0:
					for v in values:
						outp = outp + ["/".join([k,v])]
				else:
					outp = outp + [k]
			return outp

	#for testing correct conversion of data --> dict --> data, must preserve all labels
	@classmethod
	def test_converse_reversibility(cls,data):
		iterable = RefractiveIndexInfoDatabase.make_dict(data)
		data2 = RefractiveIndexInfoDatabase.make_data(iterable)

		for d in data:
			assert (d in data2)
		for d in data2:
			assert(d in data)

	
	@classmethod
	def fetch_dataset_yaml(cls,label):
		query_base_url = "https://refractiveindex.info/database/data/{0}"
		url = query_base_url.format(label)
		resp =  requests.get(url)

		response_yaml = yaml.load(resp._content)
		return response_yaml

	@classmethod
	def extract_refractive_indices(cls,response_yaml):
		data = (response_yaml["DATA"][0]["data"]).split("\n")
		wavelengths = []
		refractive_index = []
		for d in data:
			try:
				[w,n,k] = d.split(" ")
				wavelengths.append(float(w))
				refractive_index.append(float(n) + 1j*float(k))
			except:
				try:
					[w,n] = d.split(" ")
					wavelengths.append(float(w))
					refractive_index.append(float(n))
				except:
					print "failed on: ({})".format(d)
		return {"wavelength":wavelengths, "n": refractive_index}

rfdb = RefractiveIndexInfoDatabase()