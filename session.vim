" Project wide builtins
let g:pyflakes_builtins = ["_", "dynamic_property", "__", "P", "I", "lopen", "icu_lower", "icu_upper", "icu_title", "ngettext"]

python << EOFPY
import os

import vipy

source_file = vipy.vipy.eval('expand("<sfile>")')
project_dir = os.path.dirname(source_file)
src_dir = os.path.abspath(os.path.join(project_dir, 'src'))
base_dir = os.path.join(src_dir, 'calibre')

vipy.session.initialize(project_name='calibre', src_dir=src_dir,
            project_dir=project_dir, base_dir=base_dir)

def recipe_title_callback(raw):
    return eval(raw.decode('utf-8')).replace(' ', '_')

vipy.session.add_content_browser('.r', ',r', 'Recipe',
    vipy.session.glob_based_iterator(os.path.join(project_dir, 'recipes', '*.recipe')),
    vipy.session.regexp_based_matcher(r'title\s*=\s*(?P<title>.+)', 'title', recipe_title_callback))
EOFPY

nmap \log :enew<CR>:read ! bzr log -l 500 ../.. <CR>:e ../../Changelog.yaml<CR>:e constants.py<CR>
