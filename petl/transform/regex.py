from __future__ import absolute_import, print_function, division, \
    unicode_literals


import re
import operator
from petl.compat import next, string_types


from petl.util.base import Table, asindices
from petl.transform.basics import TransformError
from petl.transform.conversions import convert


def capture(table, field, pattern, newfields=None, include_original=False,
            flags=0, fill=None):
    """
    Add one or more new fields with values captured from an existing field
    searched via a regular expression. E.g.::

        >>> import petl as etl
        >>> table1 = [['id', 'variable', 'value'],
        ...           ['1', 'A1', '12'],
        ...           ['2', 'A2', '15'],
        ...           ['3', 'B1', '18'],
        ...           ['4', 'C12', '19']]
        >>> table2 = etl.capture(table1, 'variable', '(\\w)(\\d+)',
        ...                      ['treat', 'time'])
        >>> table2
        +------+---------+---------+--------+
        | 0|id | 1|value | 2|treat | 3|time |
        +======+=========+=========+========+
        | '1'  | '12'    | 'A'     | '1'    |
        +------+---------+---------+--------+
        | '2'  | '15'    | 'A'     | '2'    |
        +------+---------+---------+--------+
        | '3'  | '18'    | 'B'     | '1'    |
        +------+---------+---------+--------+
        | '4'  | '19'    | 'C'     | '12'   |
        +------+---------+---------+--------+

        >>> # using the include_original argument
        ... table3 = etl.capture(table1, 'variable', '(\\w)(\\d+)',
        ...                      ['treat', 'time'],
        ...                      include_original=True)
        >>> table3
        +------+------------+---------+---------+--------+
        | 0|id | 1|variable | 2|value | 3|treat | 4|time |
        +======+============+=========+=========+========+
        | '1'  | 'A1'       | '12'    | 'A'     | '1'    |
        +------+------------+---------+---------+--------+
        | '2'  | 'A2'       | '15'    | 'A'     | '2'    |
        +------+------------+---------+---------+--------+
        | '3'  | 'B1'       | '18'    | 'B'     | '1'    |
        +------+------------+---------+---------+--------+
        | '4'  | 'C12'      | '19'    | 'C'     | '12'   |
        +------+------------+---------+---------+--------+

    By default the field on which the capture is performed is omitted. It can
    be included using the `include_original` argument.

    The ``fill`` parameter can be used to provide a list or tuple of values to
    use if the regular expression does not match. The ``fill`` parameter
    should contain as many values as there are capturing groups in the regular
    expression. If ``fill`` is ``None`` (default) then a
    ``petl.transform.TransformError`` will be raised on the first non-matching
    value.

    """

    return CaptureView(table, field, pattern,
                       newfields=newfields,
                       include_original=include_original,
                       flags=flags,
                       fill=fill)


Table.capture = capture


class CaptureView(Table):

    def __init__(self, source, field, pattern, newfields=None,
                 include_original=False, flags=0, fill=None):
        self.source = source
        self.field = field
        self.pattern = pattern
        self.newfields = newfields
        self.include_original = include_original
        self.flags = flags
        self.fill = fill

    def __iter__(self):
        return itercapture(self.source, self.field, self.pattern,
                           self.newfields, self.include_original, self.flags,
                           self.fill)


def itercapture(source, field, pattern, newfields, include_original, flags,
                fill):
    it = iter(source)
    prog = re.compile(pattern, flags)

    flds = next(it)
    if field in flds:
        field_index = flds.index(field)
    elif isinstance(field, int) and field < len(flds):
        field_index = field
    else:
        raise Exception('field invalid: must be either field name or index')

    # determine output fields
    out_flds = list(flds)
    if not include_original:
        out_flds.remove(field)
    if newfields:
        out_flds.extend(newfields)
    yield tuple(out_flds)

    # construct the output data
    for row in it:
        value = row[field_index]
        if include_original:
            out_row = list(row)
        else:
            out_row = [v for i, v in enumerate(row) if i != field_index]
        match = prog.search(value)
        if match is None:
            if fill is not None:
                out_row.extend(fill)
            else:
                raise TransformError('value %r did not match pattern %r' % (value, pattern))
        else:
            out_row.extend(match.groups())
        yield tuple(out_row)


def split(table, field, pattern, newfields=None, include_original=False,
          maxsplit=0, flags=0):
    """
    Add one or more new fields with values generated by splitting an
    existing value around occurrences of a regular expression. E.g.::

        >>> import petl as etl
        >>> table1 = [['id', 'variable', 'value'],
        ...           ['1', 'parad1', '12'],
        ...           ['2', 'parad2', '15'],
        ...           ['3', 'tempd1', '18'],
        ...           ['4', 'tempd2', '19']]
        >>> table2 = etl.split(table1, 'variable', 'd', ['variable', 'day'])
        >>> table2
        +------+---------+------------+-------+
        | 0|id | 1|value | 2|variable | 3|day |
        +======+=========+============+=======+
        | '1'  | '12'    | 'para'     | '1'   |
        +------+---------+------------+-------+
        | '2'  | '15'    | 'para'     | '2'   |
        +------+---------+------------+-------+
        | '3'  | '18'    | 'temp'     | '1'   |
        +------+---------+------------+-------+
        | '4'  | '19'    | 'temp'     | '2'   |
        +------+---------+------------+-------+

    By default the field on which the split is performed is omitted. It can
    be included using the `include_original` argument.

    """

    return SplitView(table, field, pattern, newfields, include_original,
                     maxsplit, flags)


Table.split = split


class SplitView(Table):

    def __init__(self, source, field, pattern, newfields=None,
                 include_original=False, maxsplit=0, flags=0):
        self.source = source
        self.field = field
        self.pattern = pattern
        self.newfields = newfields
        self.include_original = include_original
        self.maxsplit = maxsplit
        self.flags = flags

    def __iter__(self):
        return itersplit(self.source, self.field, self.pattern, self.newfields,
                         self.include_original, self.maxsplit, self.flags)


def itersplit(source, field, pattern, newfields, include_original, maxsplit,
              flags):

    it = iter(source)
    prog = re.compile(pattern, flags)

    flds = next(it)
    if field in flds:
        field_index = flds.index(field)
    elif isinstance(field, int) and field < len(flds):
        field_index = field
        field = flds[field_index]
    else:
        raise Exception('field invalid: must be either field name or index')

    # determine output fields
    out_flds = list(flds)
    if not include_original:
        out_flds.remove(field)
    if newfields:
        out_flds.extend(newfields)
    yield tuple(out_flds)

    # construct the output data
    for row in it:
        value = row[field_index]
        if include_original:
            out_row = list(row)
        else:
            out_row = [v for i, v in enumerate(row) if i != field_index]
        out_row.extend(prog.split(value, maxsplit))
        yield tuple(out_row)


def sub(table, field, pattern, repl, count=0, flags=0):
    """
    Convenience function to convert values under the given field using a
    regular expression substitution. See also :func:`re.sub`.

    """

    prog = re.compile(pattern, flags)
    conv = lambda v: prog.sub(repl, v, count=count)
    return convert(table, field, conv)


Table.sub = sub


def search(table, *args, **kwargs):
    """
    Perform a regular expression search, returning rows that match a given
    pattern, either anywhere in the row or within a specific field. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar', 'baz'],
        ...           ['orange', 12, 'oranges are nice fruit'],
        ...           ['mango', 42, 'I like them'],
        ...           ['banana', 74, 'lovely too'],
        ...           ['cucumber', 41, 'better than mango']]
        >>> # search any field
        ... table2 = etl.search(table1, '.g.')
        >>> table2
        +------------+-------+--------------------------+
        | 0|foo      | 1|bar | 2|baz                    |
        +============+=======+==========================+
        | 'orange'   |    12 | 'oranges are nice fruit' |
        +------------+-------+--------------------------+
        | 'mango'    |    42 | 'I like them'            |
        +------------+-------+--------------------------+
        | 'cucumber' |    41 | 'better than mango'      |
        +------------+-------+--------------------------+

        >>> # search a specific field
        ... table3 = etl.search(table1, 'foo', '.g.')
        >>> table3
        +----------+-------+--------------------------+
        | 0|foo    | 1|bar | 2|baz                    |
        +==========+=======+==========================+
        | 'orange' |    12 | 'oranges are nice fruit' |
        +----------+-------+--------------------------+
        | 'mango'  |    42 | 'I like them'            |
        +----------+-------+--------------------------+

    The complement of search() (i.e., the rows not found via search())
    can be found via :func:`petl.transform.regex.searchcomplement`

    """

    if len(args) == 1:
        field = None
        pattern = args[0]
    elif len(args) == 2:
        field = args[0]
        pattern = args[1]
    else:
        raise Exception('expected 1 or 2 arguments')
    return SearchView(table, pattern, field=field, **kwargs)


Table.search = search


class SearchView(Table):

    def __init__(self, table, pattern, field=None, flags=0, complement=False):
        self.table = table
        self.pattern = pattern
        self.field = field
        self.flags = flags
        self.complement = complement

    def __iter__(self):
        return itersearch(self.table, self.pattern, self.field, self.flags,
                          self.complement)


def itersearch(table, pattern, field, flags, complement):
    prog = re.compile(pattern, flags)
    it = iter(table)
    fields = [str(f) for f in next(it)]
    yield tuple(fields)

    if field is None:
        # search whole row
        test = lambda r: any(prog.search(str(v)) for v in r)
    elif isinstance(field, string_types):
        # search single field
        index = fields.index(field)
        test = lambda r: prog.search(str(r[index]))
    else:  # list or tuple or ...
        # search selection of fields
        indices = asindices(fields, field)
        getvals = operator.itemgetter(*indices)
        test = lambda r: any(prog.search(str(v)) for v in getvals(r))

    # complement==False, return rows that match
    if not complement:
        for row in it:
            if test(row):
                yield tuple(row)
    # complement==True, return rows that do not match
    else:
        for row in it:
            if not test(row):
                yield tuple(row)


def searchcomplement(table, *args, **kwargs):
    """
    Perform a regular expression search, returning rows that **do not**
    match a given pattern, either anywhere in the row or within a specific
    field. E.g.::

        >>> import petl as etl
        >>> table1 = [['foo', 'bar', 'baz'],
        ...           ['orange', 12, 'oranges are nice fruit'],
        ...           ['mango', 42, 'I like them'],
        ...           ['banana', 74, 'lovely too'],
        ...           ['cucumber', 41, 'better than mango']]
        >>> # search any field
        ... table2 = etl.searchcomplement(table1, '.g.')
        >>> table2
        +----------+-------+--------------+
        | 0|foo    | 1|bar | 2|baz        |
        +==========+=======+==============+
        | 'banana' |    74 | 'lovely too' |
        +----------+-------+--------------+

        >>> # search a specific field
        ... table3 = etl.searchcomplement(table1, 'foo', '.g.')
        >>> table3
        +------------+-------+---------------------+
        | 0|foo      | 1|bar | 2|baz               |
        +============+=======+=====================+
        | 'banana'   |    74 | 'lovely too'        |
        +------------+-------+---------------------+
        | 'cucumber' |    41 | 'better than mango' |
        +------------+-------+---------------------+

    This returns the complement of :func:`petl.transform.regex.search`.

    """

    return search(table, *args, complement=True, **kwargs)


Table.searchcomplement = searchcomplement
