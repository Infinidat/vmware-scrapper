# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: http://doc.scrapy.org/topics/item-pipeline.html
import os, keyword
from jinja2 import Environment, PackageLoader
from scrapy.conf import settings
from utils import camel_to_under, quote
from ConfigParser import ConfigParser
config = ConfigParser()
config.read( os.path.join(os.path.abspath(os.path.dirname(__file__)), '..', 'visdk41.cfg'))

class VisdkPipeline(object):
    mo_base = 'BaseEntity'
    do_base = 'BaseData'

    def _setup(self, item):
        # generate class code
        codedir = os.path.join(settings['OUTPUT_DIR'], config.get(item['type'], 'code_dir'))
        codename = codedir + '/%s.py' % camel_to_under(item['name'])

        docdir = os.path.join(settings['DOC_DIR'], config.get(item['type'], 'doc_dir'))
        docname = docdir + '/%s.rst' % camel_to_under(item['name'])

        if not os.path.exists(codedir):
            os.mkdir(codedir)
        if not os.path.exists(docdir):
            os.mkdir(docdir)

        return codename, docname

    def process_item(self, item, spider=None):
        #if item['type'] == 'mo':
        #    self.process_mo_item(item)
        # we no longer do this in the pipeline because we need to find out the parent
        # class to get a valid argument list...  it's now handled after scraping in extensions
        #elif item['type'] == 'do':
        #    self.process_do_item(item)
        return item

    def _get_type(self, _type):
        if _type is None or _type == "None":
            return "void"
        if _type.endswith("dateTime"):
            return "vmodl.DateTime"
        if _type.startswith("xsd:"):
            return _type[len("xsd:"):]
        if " to a " in _type:
            return _type.split(" to a ")[-1]
        return _type

    def _get_vmodl_name(self, item):
        return os.path.splitext(item['url'].split("/")[-1])[0]

    def create_mo_method_arguments_string(self, meth):
        arguments = []
        if len(meth.arguments) == 0:
            return "()"
        for arg in meth.arguments:
            is_opt = "F_OPTIONAL" if arg.optional else "0"
            _type = self._get_type(arg.type)
            arguments.append('("{}", "{}", "sms.version.version4", {}, None)'.format(arg.name, _type, is_opt))
        return "(\n\t\t\t{},\n\t\t)".format(",\n\t\t\t".join(arguments))

    def create_mo_method_fault_string(self, meth):
        if len(meth.faults) == 0:
            return "None"
        return "[{}]".format(", ".join(['"{}"'.format(f.type) for f in meth.faults]))

    def create_mo_method_string(self, item):
        methods = []
        for meth in item["methods"]:
            # mVmodl, mWsdl, mVersion, mParams, mResult, mPrivilege, mFaults
            mFaults = self.create_mo_method_fault_string(meth)
            mParams = self.create_mo_method_arguments_string(meth)
            mVersion = "sms.version.version4"
            mResult = '(0, "{0}", "{0}")'.format(self._get_type(meth.return_value.type))
            mPrivilege = meth.privileges[0]
            methods.append('("{}", "{}", "{}", {}, {}, "{}", {})'.format(meth.name, meth.name, mVersion, mParams, mResult, mPrivilege, mFaults))
        return "[\n\t\t{}\n\t]".format(",\n\t\t".join(methods))

    def create_mo_field_string(self, item):
        if len(item["properties"]) > 1:
            import pdb; pdb.set_trace()
        return "[]"

    def create_mo_string(self, item):
        # vmodlName, wsdlName, parent, version, props, methods
        wsdlName = item["name"]
        vmodlName = self._get_vmodl_name(item)
        parent = item['info'].get('Extends', "vmodl.ManagedObject")
        version = "sms.version.version4"
        props = self.create_mo_field_string(item)
        methods = self.create_mo_method_string(item)
        return 'CreateManagedType(\n\t"{0}",\n\t"{1}",\n\t"{2}",\n\t"{3}",\n\t{4},\n\t{5}\n)\n'.format(vmodlName, wsdlName, parent, version, props, methods)

    def create_do_field_string(self, item):
        fields = []
        for arg in item["properties"]:
            is_opt = "F_OPTIONAL" if arg.optional else "0"
            _type = self._get_type(arg.type)
            fields.append('("{}", "{}", "sms.version.version4", {})'.format(arg.name, _type, is_opt))
        return "[\n\t\t{}\n\t]".format(",\n\t\t".join(fields))

    def create_do_string(self, item):
        # vmodlName, wsdlName, parent, version, props
        vmodlName = self._get_vmodl_name(item)
        wsdlName = item["name"]
        parent = item['info'].get('Extends', "vmodl.DynamicData")
        version = "sms.version.version4"
        props = self.create_do_field_string(item)
        return 'CreateDataType(\n\t"{0}",\n\t"{1}",\n\t"{2}",\n\t"{3}",\n\t{4}\n)\n'.format(vmodlName, wsdlName, parent, version, props)

    def create_enum_string(self, item):
        # vmodlName, wsdlName, version, values
        vmodlName = self._get_vmodl_name(item)
        wsdlName = item["name"]
        version = "sms.version.version4"
        values = ['"{}"'.format(const.name) for const in item["constants"]]
        values = "[\n\t\t{}\n\t]".format(",\n\t\t".join(values))
        return 'CreateEnumType(\n\t"{0}",\n\t"{1}",\n\t"{2}",\n\t{3}\n)\n'.format(vmodlName, wsdlName, version, values)

    def write_to_file(self, str):
        if True:
            str = str.replace("\n", "").replace("\t", "").replace(",", ", ") + "\n"
        open("ServerObjects.py", "a+").write(str)


    def process_mo_item(self, item, items):
        props = []
        codename, docname = self._setup(item)

        for prop in item['properties']:
            # beware of keywords...
            if prop.name in keyword.kwlist + ['property']:
                prop.name = prop.name + "_"
            props.append(prop)

        _type = item['type']
        _base = item['info'].get('Extends', self.mo_base)
        if _base == self.mo_base:
            _type = 'base'

        self.write_to_file(self.create_mo_string(item))
        return item

    def process_do_item(self, item, items):
        codename, docname = self._setup(item)

        _type = item['type']
        _base = item['info'].get('Extends', self.mo_base)
        if _base == self.mo_base:
            _type = 'base'

        if self._get_vmodl_name(item).startswith("vmodl"):
            return

        self.write_to_file(self.create_do_string(item))

        return item

    def process_enum_item(self, item, items):
        codename, docname = self._setup(item)

        self.write_to_file(self.create_enum_string(item))
        return item

    def _get_props(self, item, items):
        props = []
        if item['info'].has_key('Extends'):
            extends = item['info']['Extends']

            # no multiple inheritence that I could see...
            parent = items.get(extends, None)
            if parent:
                props += self._get_props(parent, items)

        myprops = []
        for prop in item['properties']:
            myprops.append(prop)
        return myprops + props

    def _generate_docs(self, docname, env, item):
        #########################################
        # generate documentation
        #########################################
        with open(docname, 'w') as fp:
            if item['type'] == 'mo':
                doc_template = env.get_template('mo_doc.template')
                t = doc_template.render(classname=item['name'], directives=self._get_directives(item), methods=item['methods'])
            elif item['type'] == 'do':
                doc_template = env.get_template('do_doc.template')
                t = doc_template.render(classname=item['name'], directives=self._get_directives(item), properties=item['properties'])
            elif item['type'] == 'enum':
                doc_template = env.get_template('enum_doc.template')
                t = doc_template.render(classname=item['name'], constants=item['constants'], description=item['description'])
            t = t.encode("ascii", "ignore")
            fp.write(t)
        return item

    def _get_directives(self, item):
        directives = []
        for name, value in item['info'].items():
            rvals = []
            value = ''.join(value)
            values = [x.strip() for x in value.split(',')]
            for value in values:
                if name in ['Returned by', 'Parameter to']:
                    rvals.append(":py:meth:`~pyvisdk.do.%s.%s`" % (camel_to_under(value), value))

                elif name in ['Extends']:
                    rvals.append(":py:class:`~pyvisdk.mo.%s.%s`" % (camel_to_under(value), value))

                elif name in ['See also', 'Property of', 'Extended by']:
                    rvals.append(":py:class:`~pyvisdk.do.%s.%s`" % (camel_to_under(value), value))
                else:
                    rvals.append(value)
            directives.append( (name, rvals) )
        return directives


