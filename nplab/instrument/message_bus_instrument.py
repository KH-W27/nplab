# -*- coding: utf-8 -*-
"""
Message Bus Instrument
======================

This base class

@author: Richard Bowman
"""
#from traits.api import HasTraits, Bool, Int, Str, Button, Array, Enum, List
#import nplab
import re
import nplab.instrument
from functools import partial


class MessageBusInstrument(nplab.instrument.Instrument):
    """
    Message Bus Instrument
    ======================

    An instrument that communicates by sending strings back and forth over a bus.

    This base class provides commonly-used mechanisms that support the use of
    serial or VISA instruments.  The SerialInstrument and VISAInstrument classes
    both inherit from this class.

    Subclassing Notes
    -----------------

    The minimum you need to do to create a working subclass is override the
    `write()` and `readline()` methods.  You probably also want to provide an
    open() and close() method to deal with the underlying port, and put
    something sensible in __init__ to open your port when it's created.

    It's also a very good idea to provide some way to flush the input buffer
    with `flush_input_buffer()`.
    """
    termination_character = "\n" #: All messages to or from the instrument end with this character.
    termination_line = None #: If multi-line responses are recieved, they must end with this string

    def write(self,query_string):
        """Write a string to the serial port"""
        raise NotImplementedError("Subclasses of MessageBusInstrument must override the write method!")
    def flush_input_buffer(self):
        """Make sure there's nothing waiting to be read.

        This function should be overridden to make sure nothing's lurking in
        the input buffer that could confuse a query.
        """
        pass
    def readline(self, timeout=None):
        """Read one line from the underlying bus.  Must be overriden."""
        raise NotImplementedError("Subclasses of MessageBusInstrument must override the readline method!")
    def read_multiline(self, termination_line=None, timeout=None):
        """Read one line from the underlying bus.  Must be overriden.

        This should not need to be reimplemented unless there's a more efficient
        way of reading multiple lines than multiple calls to readline()."""
        if termination_line is None:
            termination_line = self.termination_line
        assert isinstance(termination_line, str), "If you perform a multiline query, you must specify a termination line either through the termination_line keyword argument or the termination_line property of the NPSerialInstrument."
        response = ""
        last_line = "dummy"
        while termination_line not in last_line and len(last_line) > 0: #read until we get the termination line.
            last_line = self.readline(timeout)
            response += last_line
        return response
    def query(self,queryString,multiline=False,termination_line=None,timeout=None):
        """
        Write a string to the stage controller and return its response.

        It will block until a response is received.  The multiline and termination_line commands
        will keep reading until a termination phrase is reached.
        """
        self.flush_input_buffer()
        self.write(queryString)
        if termination_line is not None:
            multiline = True
        if multiline:
            return self.read_multiline(termination_line)
        else:
            return self.readline(timeout).strip() #question: should we strip the final newline?
    def parsed_query_old(self, query_string, response_string=r"(\d+)", re_flags=0, parse_function=int, **kwargs):
        """
        Perform a query, then parse the result.

        By default it looks for an integer and returns one, otherwise it will
        match a custom regex string and return the subexpressions, parsed through
        the supplied functions.

        TODO: make this accept friendlier sscanf style arguments, and produce parse functions automatically
        """
        reply = self.query(query_string, **kwargs)
        res = re.search(response_string, reply, flags=re_flags)
        if res is None:
            raise ValueError("Stage response to '%s' ('%s') wasn't matched by /%s/" % (query_string, reply, response_string))
        try:
            if len(res.groups()) == 1:
                return parse_function(res.groups()[0])
            else:
                return map(parse_function,res.groups())
        except ValueError:
            raise ValueError("Stage response to %s ('%s') couldn't be parsed by the supplied function" % (query_string, reply))
    def parsed_query(self, query_string, response_string=r"%d", re_flags=0, parse_function=None, **kwargs):
        """
        Perform a query, returning a parsed form of the response.

        First query the instrument with the given query string, then compare
        the response against a template.  The template may contain text and
        placeholders (e.g. %i and %f for integer and floating point values
        respectively).  Regular expressions are also allowed - each group is
        considered as one item to be parsed.  However, currently it's not
        supported to use both % placeholders and regular expressions at the
        same time.

        If placeholders %i, %f, etc. are used, the returned values are
        automatically converted to integer or floating point, otherwise you
        must specify a parsing function (applied to all groups) or a list of
        parsing functions (applied to each group in turn).
        """

        response_regex = response_string
        noop = lambda x: x #placeholder null parse function
        placeholders = [ #tuples of (regex matching placeholder, regex to replace it with, parse function)
            (r"%c",r".", noop),
            (r"%(\d+)c",r".{\1}", noop), #TODO support %cn where n is a number of chars
            (r"%d",r"[-+]?\d+", int),
            (r"%[eEfg]",r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", float),
            (r"%i",r"[-+]?(?:0[xX][\dA-Fa-f]+|0[0-7]*|\d+)", lambda x: int(x, 0)), #0=autodetect base
            (r"%o",r"[-+]?[0-7]+", lambda x: int(x, 8)), #8 means octal
            (r"%s",r"\S+",noop),
            (r"%u",r"\d+",int),
            (r"%[xX]",r"[-+]?(?:0[xX])?[\dA-Fa-f]+",lambda x: int(x, 16)), #16 forces hexadecimal
        ]
        matched_placeholders = []
        for placeholder, regex, parse_fun in placeholders:
            response_regex = re.sub(placeholder, '('+regex+')', response_regex) #substitute regex for placeholder
            matched_placeholders.extend([(parse_fun, m.start()) for m in re.finditer(placeholder, response_string)]) #save the positions of the placeholders
        if parse_function is None:
            parse_function = [f for f, s in sorted(matched_placeholders, key=lambda m: m[1])] #order parse functions by their occurrence in the original string
        if not hasattr(parse_function,'__iter__'):
            parse_function = [parse_function] #make sure it's a list.

        reply = self.query(query_string, **kwargs) #do the query
        res = re.search(response_regex, reply, flags=re_flags)
        if res is None:
            raise ValueError("Stage response to '%s' ('%s') wasn't matched by /%s/ (generated regex /%s/" % (query_string, reply, response_string, response_regex))
        try:
            parsed_result= [f(g) for f, g in zip(parse_function, res.groups())] #try to apply each parse function to its argument
            if len(parsed_result) == 1:
                return parsed_result[0]
            else:
                return parsed_result
        except ValueError:
            print "Parsing Error"
            print "Matched Groups:", res.groups()
            print "Parsing Functions:", parse_function
            raise ValueError("Stage response to %s ('%s') couldn't be parsed by the supplied function" % (query_string, reply))
    def int_query(self, query_string, **kwargs):
        """Perform a query and return the result(s) as integer(s) (see parsedQuery)"""
        return self.parsed_query(query_string, "%d", **kwargs)
    def float_query(self, query_string, **kwargs):
        """Perform a query and return the result(s) as float(s) (see parsedQuery)"""
        return self.parsed_query(query_string, "%f", **kwargs)

    #@staticmethod  # this was an attempt at making a property factory - now using a descriptor
    #def queried_property(self, get_cmd, set_cmd, dtype='float', docstring=''):
    #    get_func = self.float_query if dtype=='float' else self.query
    #    return property(fget=partial(get_func, get_cmd), fset=self.write, docstring=docstring)


class queried_property(object):
    def __init__(self, get_cmd=None, set_cmd=None, fvalidate=None, fdel=None, doc=None, dtype='float'):
        self.dtype = dtype
        self.get_cmd = get_cmd
        self.set_cmd = set_cmd
        self.fvalidate = fvalidate
        self.fdel = fdel
        self.__doc__ = doc

    def __get__(self, obj, objtype=None):
        if obj is None:
            return self
        if self.get_cmd is None:
            raise AttributeError("unreadable attribute")
        if self.dtype == 'float':
            getter = obj.float_query
        elif self.dtype == 'int':
            getter = obj.int_query
        else:
            getter = obj.query
        return getter(self.get_cmd)

    def __set__(self, obj, value):
        print 'set', obj, value
        if self.set_cmd is None:
            raise AttributeError("can't set attribute")
        if self.fvalidate is not None:
            self.fvalidate(obj, value)
        message = self.set_cmd
        if '{0' in message:
            message = message.format(value)
        elif '%' in message:
            message = message % value
        print message
        obj.write(message)

    def __delete__(self, obj):
        if self.fdel is None:
            raise AttributeError("can't delete attribute")
        self.fdel(obj)


class queried_channel_property(queried_property):
    def __init__(self, get_cmd=None, set_cmd=None, fvalidate=None, fdel=None, doc=None, dtype='float'):
        super(queried_channel_property, self).__init__(get_cmd, set_cmd, fvalidate, fdel, doc, dtype)

    def __get__(self, obj, objtype=None):
        assert hasattr(obj, 'ch') and hasattr(obj, 'parent'),\
        'object must have a ch attribute and a parent attribute'
        if obj is None:
            return self
        if self.get_cmd is None:
            raise AttributeError("unreadable attribute")
        if self.dtype == 'float':
            getter = obj.parent.float_query
        elif self.dtype == 'int':
            getter = obj.parent.int_query
        else:
            getter = obj.parent.query
        message = self.get_cmd
        if '{0' in message:
            message = message.format(obj.ch)
        elif '%' in message:
            message = message % obj.ch
        return getter(message)

    def __set__(self, obj, value):
        assert hasattr(obj, 'ch') and hasattr(obj, 'parent'),\
        'object must have a ch attribute and a parent attribute'
        if self.set_cmd is None:
            raise AttributeError("can't set attribute")
        if self.fvalidate is not None:
            self.fvalidate(obj, value)
        message = self.set_cmd
        if '{0' in message:
            message = message.format(obj.ch, value)
        elif '%' in message:
            message = message % (obj.ch, value)
        obj.parent.write(message)


class EchoInstrument(MessageBusInstrument):
    """Trivial test instrument, it simply echoes back what we write."""
    def __init__(self):
        super(EchoInstrument, self).__init__()
        self._last_write = ""
    def write(self, msg):
        self._last_write = msg
    def readline(self, timeout=None):
        return self._last_write


if __name__ == '__main__':
    class DummyInstrument(EchoInstrument):
        x = queried_property('gx', 'sx {0}', dtype='str')

    instr = DummyInstrument()
    print instr.x
    instr.x = 'y'
    print instr.x
    instr.x = 'x'
    print instr.x