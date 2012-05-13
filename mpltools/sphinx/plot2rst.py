"""
Example generation from python files.

Generate the rst files for the examples by iterating over the python
example files. Files that generate images should start with 'plot'.

To generate your own examples, just add ``'mpltools.sphinx.plot2rst'``` to the
list of ``extensions``in your Sphinx configuration file.

This code was adapted from scikits-image, which took it from scikits-learn.

Options
-------
The ``plot2rst`` extension accepts the following options:

plot2rst_paths : length-2 tuple
    Paths to (python plot, generated rst) files, i.e. (source, destination).
    Note that both paths are relative to Sphinx 'source' path.

plot2rst_rcparams : dict
    Matplotlib configuration parameters. See
    http://matplotlib.sourceforge.net/users/customizing.html for details.

plot2rst_default_thumb : str
    Path (relative to doc root) of default thumbnail image.

plot2rst_thumb_scale : float
    Scale factor for thumbnail (e.g., 0.2 to scale plot to 1/5th the
    original size).

plot2rst_plot_tag : str
    When this tag is found in the example file, the current plot is saved and
    tag is replaced with plot path. Defaults to 'PLOT2RST.current_figure'.
"""
import os
import shutil
import traceback
import glob
import token
import tokenize

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import image


plot_rst_template = """
.. _example_%(short_filename)s:

%(docstring)s

%(image_list)s

.. literalinclude:: %(src_name)s
    :lines: %(end_row)s-

"""

tutorial_rst_template = """
.. _example_%(short_filename)s:

%(rst)s

"""

CODE_LINK = """

**Python source code:** :download:`download <{0}>`
(generated using ``mpltools`` |version|)

"""

toctree_template = """
.. toctree::
   :hidden:

   %s

"""


CLEAR_SECTION = """
.. raw:: html

    <div style="clear: both"></div>

"""


IMAGE_TEMPLATE = """
.. image:: images/%s
    :align: center

"""

GALLERY_HEADER = """

Examples
========

.. _examples-index:

"""


class Path(str):
    """Path object for manipulating directory and file paths."""

    def __init__(self, path):
        super(Path, self).__init__(path)

    @property
    def isdir(self):
        return os.path.isdir(self)

    @property
    def exists(self):
        """Return True if path exists"""
        return os.path.exists(self)

    def pjoin(self, *args):
        """Join paths. `p` prefix prevents confusion with string method."""
        return self.__class__(os.path.join(self, *args))

    def psplit(self):
        """Split paths. `p` prefix prevents confusion with string method."""
        return [self.__class__(p) for p in os.path.split(self)]

    def makedirs(self):
        if not self.exists:
            os.makedirs(self)

    def listdir(self):
        return os.listdir(self)

    def format(self, *args, **kwargs):
        return self.__class__(super(Path, self).format(*args, **kwargs))

    def __add__(self, other):
        return self.__class__(super(Path, self).__add__(other))

    def __iadd__(self, other):
        return self.__add__(other)


def setup(app):
    app.connect('builder-inited', generate_rst_gallery)

    app.add_config_value('plot2rst_paths',
                         ('../examples', 'auto_examples'), True)
    app.add_config_value('plot2rst_rcparams', {}, True)
    app.add_config_value('plot2rst_default_thumb', None, True)
    app.add_config_value('plot2rst_thumb_scale', 0.2, True)
    app.add_config_value('plot2rst_plot_tag', 'PLOT2RST.current_figure', True)


def generate_rst_gallery(app):
    """Add list of examples and gallery to Sphinx app."""
    cfg = app.builder.config

    doc_src = Path(os.path.abspath(app.builder.srcdir)) # path/to/doc/source

    plot_path, rst_path = [Path(p) for p in cfg.plot2rst_paths]
    rst_dir = doc_src.pjoin(rst_path)
    example_dir = doc_src.pjoin(plot_path)

    if not example_dir.exists:
        print "No example directory found at", example_dir
        return
    rst_dir.makedirs()

    # we create an index.rst with all examples
    gallery_index = file(rst_dir.pjoin('index'+cfg.source_suffix), 'w')
    gallery_index.write(GALLERY_HEADER)

    # Here we don't use an os.walk, but we recurse only twice: flat is
    # better than nested.
    write_gallery(gallery_index, example_dir, rst_dir, cfg)
    for d in sorted(example_dir.listdir()):
        example_sub = example_dir.pjoin(d)
        if example_sub.isdir:
            rst_sub = rst_dir.pjoin(d)
            rst_sub.makedirs()
            write_gallery(gallery_index, example_sub, rst_sub, cfg, depth=1)
    gallery_index.flush()


def write_gallery(gallery_index, src_dir, rst_dir, cfg, depth=0):
    """Generate the rst files for an example directory, i.e. gallery.

    Write rst files from python examples and add example links to gallery.

    Parameters
    ----------
    gallery_index : file
        Index file for plot gallery.
    src_dir : 'str'
        Source directory for python examples.
    rst_dir : 'str'
        Destination directory for rst files generated from python examples.
    cfg : config object
        Sphinx config object created by Sphinx.
    """
    index_name = 'index' + cfg.source_suffix
    gallery_template = src_dir.pjoin(index_name)
    if not os.path.exists(gallery_template):
        print src_dir
        print 80*'_'
        print ('Example directory %s does not have a %s file'
                        % (src_dir, index_name))
        print 'Skipping this directory'
        print 80*'_'
        return

    gallery_description = file(gallery_template).read()
    gallery_index.write('\n\n%s\n\n' % gallery_description)

    rst_dir.makedirs()
    examples = [fname for fname in sorted(src_dir.listdir(), key=plots_first)
                      if fname.endswith('py')]
    ex_names = [ex[:-3] for ex in examples] # strip '.py' extension
    if depth == 0:
        sub_dir = Path('')
    else:
        sub_dir_list = src_dir.psplit()[-depth:]
        sub_dir = Path('/'.join(sub_dir_list) + '/')
    gallery_index.write(toctree_template % (sub_dir + '\n   '.join(ex_names)))

    write = gallery_index.write
    for src_name in examples:
        rst_file_from_example(src_name, src_dir, rst_dir, cfg)
        thumb = sub_dir.pjoin('images/thumb', src_name[:-3] + '.png')
        gallery_index.write('.. figure:: %s\n' % thumb)

        link_name = sub_dir.pjoin(src_name)
        link_name = link_name.replace(os.path.sep, '_')
        if link_name.startswith('._'):
            link_name = link_name[2:]

        write('   :figclass: gallery\n')
        write('   :target: ./%s.html\n\n' % (sub_dir + src_name[:-3]))
        write('   :ref:`example_%s`\n\n' % (link_name))
    write(CLEAR_SECTION) # clear at the end of the section


def plots_first(fname):
    """Decorate filename so that examples with plots are displayed first."""
    if not (fname.startswith('plot') and fname.endswith('.py')):
        return 'zz' + fname
    return fname


def rst_file_from_example(src_name, src_dir, rst_dir, cfg):
    """Write rst file from a given python example.

    Parameters
    ----------
    src_name : str
        Name of example file.
    src_dir : 'str'
        Source directory for python examples.
    rst_dir : 'str'
        Destination directory for rst files generated from python examples.
    cfg : config object
        Sphinx config object created by Sphinx.
    """
    last_dir = src_dir.psplit()[-1]
    # to avoid leading . in file names, and wrong names in links
    if last_dir == '.' or last_dir == 'examples':
        last_dir = Path('')
    else:
        last_dir += '_'

    info = dict(src_name=src_name)
    info['short_filename'] = last_dir + src_name # dir_subdir_srcname
    src_path = src_dir.pjoin(src_name)
    example_file = rst_dir.pjoin(src_name)
    shutil.copyfile(src_path, example_file)

    image_dir = rst_dir.pjoin('images')
    thumb_dir = image_dir.pjoin('thumb')
    image_dir.makedirs()
    thumb_dir.makedirs()

    base_image_name = os.path.splitext(src_name)[0]
    image_path = image_dir.pjoin(base_image_name + '_{0}.png')

    basename, py_ext = os.path.splitext(src_name)
    rst_path = rst_dir.pjoin(basename + cfg.source_suffix)

    if plots_are_current(src_path, image_path) and rst_path.exists:
        return

    blocks = split_code_and_text(example_file)
    if blocks[0][2].startswith('#!'):
        blocks.pop(0) # don't add shebang line to rst file.

    has_inline_plots = any(cfg.plot2rst_plot_tag in b[2] for b in blocks)
    if has_inline_plots:
        figure_list, rst = process_blocks(blocks, src_path, image_path, cfg)
        info['rst'] = rst
        example_rst = tutorial_rst_template % info
    else:
        # print first block of text, display all plots, then display code.
        first_text_block = [b for b in blocks if b[0] == 'text'][0]
        label, (start, end), content = first_text_block
        info['docstring'] = content.strip().strip('"""')
        info['end_row'] = end + 1 # + 1 b/c lines start at 1, not 0.
        figure_list = save_plot(src_path, image_path, cfg)
        rst_blocks = [IMAGE_TEMPLATE % f.lstrip('/') for f in figure_list]
        info['image_list'] = ''.join(rst_blocks)
        example_rst = plot_rst_template % info

    example_rst += CODE_LINK.format(src_name)

    f = open(rst_path,'w')
    f.write(example_rst)
    f.flush()

    thumb_path = thumb_dir.pjoin(src_name[:-3] + '.png')
    first_image_file = image_dir.pjoin(figure_list[0].lstrip('/'))
    if first_image_file.exists:
        image.thumbnail(first_image_file, thumb_path, cfg.plot2rst_thumb_scale)

    if not thumb_path.exists:
        if cfg.plot2rst_default_thumb is None:
            print "WARNING: No plots found and default thumbnail not defined."
            print "Specify 'plot2rst_default_thumb' in Sphinx config file."
        else:
            shutil.copy(cfg.plot2rst_default_thumb, thumb_path)


def plots_are_current(src_path, image_path):
    first_image_file = Path(image_path.format(1))
    needs_replot = (not first_image_file.exists or
                    mod_time(first_image_file) <= mod_time(src_path))
    return not needs_replot


def mod_time(file_path):
    return os.stat(file_path).st_mtime


def split_code_and_text(source_file):
    """Return list with source file separated into code and text blocks.

    Returns
    -------
    blocks : list of (label, (start, end+1), content)
        List where each element is a tuple with the label ('text' or 'code'),
        the (start, end+1) line numbers, and content string of block.
    """
    block_edges, idx_first_text_block = get_block_edges(source_file)

    with open(source_file) as f:
        source_lines = f.readlines()

    # Every other block should be a text block
    idx_text_block = np.arange(idx_first_text_block, len(block_edges), 2)
    blocks = []
    slice_ranges = zip(block_edges[:-1], block_edges[1:])
    for i, (start, end) in enumerate(slice_ranges):
        block_label = 'text' if i in idx_text_block else 'code'
        # subtract 1 from indices b/c line numbers start at 1, not 0
        content = ''.join(source_lines[start-1:end-1])
        blocks.append((block_label, (start, end), content))
    return blocks


def get_block_edges(source_file):
    """Return starting line numbers of code and text blocks

    Returns
    -------
    block_edges : list of int
        Line number for the start of each block. Note the
    idx_first_text_block : {0 | 1}
        0 if first block is text then, else 1 (second block better be text).
    """
    block_edges = []
    with open(source_file) as f:
        token_iter = tokenize.generate_tokens(f.readline)
        for token_tuple in token_iter:
            t_id, t_str, (srow, scol), (erow, ecol), src_line = token_tuple
            if (token.tok_name[t_id] == 'STRING' and scol == 0):
                # Add one point to line after text (for later slicing)
                block_edges.extend((srow, erow+1))
    idx_first_text_block = 0
    # when example doesn't start with text block.
    if not block_edges[0] == 1:
        block_edges.insert(0, 1)
        idx_first_text_block = 1
    # when example doesn't end with text block.
    if not block_edges[-1] == erow: # iffy: I'm using end state of loop
        block_edges.append(erow)
    return block_edges, idx_first_text_block


def process_blocks(blocks, src_path, image_path, cfg):
    """Run source, save plots as images, and convert blocks to rst.

    Parameters
    ----------
    blocks : list of block tuples
        Code and text blocks from python file. See `split_code_and_text`.
    src_path : str
        Path to example file.
    image_path : str
        Path where plots are saved (format string which accepts figure number).
    cfg : config object
        Sphinx config object created by Sphinx.

    Returns
    -------
    figure_list : list
        List of figure names saved by the example.
    rst_text : str
        Text with code wrapped code-block directives.
    """
    src_dir, src_name = src_path.psplit()
    if not src_name.startswith('plot'):
        return [], ''

    # index of blocks which have inline plots
    inline_tag = cfg.plot2rst_plot_tag
    idx_inline_plot = [i for i, b in enumerate(blocks)
                       if inline_tag in b[2]]

    image_dir, image_fmt_str = image_path.psplit()

    figure_list = []
    plt.rcdefaults()
    plt.rcParams.update(cfg.plot2rst_rcparams)
    plt.close('all')

    example_globals = {}
    rst_blocks = []
    fig_num = 1
    for i, (blabel, brange, bcontent) in enumerate(blocks):
        if blabel == 'code':
            exec(bcontent, example_globals)
            rst_blocks.append(codestr2rst(bcontent))
        else:
            if i in idx_inline_plot:
                plt.savefig(image_path.format(fig_num))
                figure_name = image_fmt_str.format(fig_num)
                fig_num += 1
                figure_list.append(figure_name)
                figure_link = os.path.join('images', figure_name)
                bcontent = bcontent.replace(inline_tag, figure_link)
            rst_blocks.append(docstr2rst(bcontent))
    return figure_list, '\n'.join(rst_blocks)


def codestr2rst(codestr):
    """Return reStructuredText code block from code string"""
    code_directive = ".. code-block:: python\n\n"
    indented_block = '\t' + codestr.replace('\n', '\n\t')
    return code_directive + indented_block


def docstr2rst(docstr):
    """Return reStructuredText from docstring"""
    if docstr[1] == docstr[0]:
        quotes = docstr[:3]
    else:
        quotes = docstr[0]
    docstr_without_trailing_whitespace = docstr.rstrip()
    idx_whitespace = len(docstr_without_trailing_whitespace) - len(docstr)
    whitespace = docstr[idx_whitespace:]
    return docstr_without_trailing_whitespace.strip(quotes) + whitespace


def save_plot(src_path, image_path, cfg):
    """Save plots as images.

    Parameters
    ----------
    src_path : str
        Path to example file.
    image_path : str
        Path where plots are saved (format string which accepts figure number).
    cfg : config object
        Sphinx config object created by Sphinx.

    Returns
    -------
    figure_list : list
        List of figure names saved by the example.
    """

    src_dir, src_name = src_path.psplit()
    if not src_name.startswith('plot'):
        return []

    first_image_file = image_path.format(1)

    needs_replot = (not os.path.exists(first_image_file) or
                    mod_time(first_image_file) <= mod_time(src_path))
    if needs_replot:
        print 'plotting %s' % src_name
        plt.rcdefaults()
        plt.rcParams.update(cfg.plot2rst_rcparams)
        plt.close('all')

        exec_source_in_dir(src_name, src_dir)
        figure_list = save_all_figures(image_path)
    else:
        image_dir, image_fmt_str = image_path.psplit()
        figure_list = [f[len(image_dir):]
                       for f in glob.glob(image_path.format('[1-9]'))]
    return figure_list


def exec_source_in_dir(source_file, source_path):
    """Execute source file in source directory and capture & print errors."""
    cwd = os.getcwd()
    try:
        # Plot example in source directory.
        os.chdir(source_path)
        execfile(source_file, {})
    except:
        print 80*'_'
        print '%s is not compiling:' % source_file
        traceback.print_exc()
        print 80*'_'
    finally:
        os.chdir(cwd)


def save_all_figures(image_path):
    """Save all matplotlib figures.

    Parameters
    ----------
    image_path : str
        Path where plots are saved (format string which accepts figure number).
    """
    figure_list = []
    image_dir, image_fmt_str = image_path.psplit()
    fig_mngr = matplotlib._pylab_helpers.Gcf.get_all_fig_managers()
    for fig_num in (m.num for m in fig_mngr):
        # Set the fig_num figure as the current figure as we can't
        # save a figure that's not the current figure.
        plt.figure(fig_num)
        plt.savefig(image_path.format(fig_num))
        figure_list.append(image_fmt_str.format(fig_num))
    return figure_list

