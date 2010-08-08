#########################################################################
#                                                                       #
#                                                                       #
#   copyright 2002 Paul Henry Tremblay                                  #
#                                                                       #
#   This program is distributed in the hope that it will be useful,     #
#   but WITHOUT ANY WARRANTY; without even the implied warranty of      #
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU    #
#   General Public License for more details.                            #
#                                                                       #
#   You should have received a copy of the GNU General Public License   #
#   along with this program; if not, write to the Free Software         #
#   Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA            #
#   02111-1307 USA                                                      #
#                                                                       #
#                                                                       #
#########################################################################
import os, re, tempfile

from calibre.ebooks.rtf2xml import copy
from calibre.utils.mreplace import MReplace

class Tokenize:
    """Tokenize RTF into one line per field. Each line will contain information useful for the rest of the script"""
    def __init__(self,
            in_file,
            bug_handler,
            copy = None,
            #run_level = 1,
    ):
        self.__file = in_file
        self.__bug_handler = bug_handler
        self.__copy = copy
        self.__write_to = tempfile.mktemp()
        self.__compile_expressions()
        #variables
        self.__uc_char = 0
        self.__uc_bin = False
        self.__uc_value = [1]
        
    def __from_ms_to_utf8(self,match_obj):
        uni_char = int(match_obj.group(1))
        if uni_char < 0:
            uni_char +=  65536
        return   '&#x' + str('%X' % uni_char) + ';'
        
    def __reini_utf8_counters(self):
        self.__uc_char = 0
        self.__uc_bin = False

    def __unicode_process(self, token):
        #change scope in
        if token == '\{':
            self.__uc_value.append(self.__uc_value[-1])
            #basic error handling
            self.__reini_utf8_counters()
            return token
        #change scope out: evaluate dict and rebuild
        elif token == '\}':
            #self.__uc_value.pop()
            self.__reini_utf8_counters()
            return token
        #add a uc control
        elif token[:3] == '\uc':
            self.__uc_value[-1] = int(token[3:])
            self.__reini_utf8_counters()
            return token
        #handle uc skippable char
        elif self.__uc_char:
            #if token[:1] == "\" and token[:1] == "\"
            pass
        #go for real \u token
        match_obj = self.__utf_exp.match(token)
        if match_obj is not None:
            #get value and handle negative case
            uni_char = int(match_obj.group(1))
            uni_len = len(match_obj.group(1)) + 2
            if uni_char < 0:
                uni_char += 65536
            uni_char = unichr(uni_char).encode('ascii', 'xmlcharrefreplace')
            #if not uc0
            if self.__uc_value[-1]:
                self.__uc_char = self.__uc_value[-1]
            #there is only an unicode char
            if len(token)<= uni_len:
                return uni_char
            #an unicode char and something else
            #must be after as it is splited on \
            elif not self.__uc_value[-1]:
                print('not only token uc0 token: ' + uni_char + token[uni_len:])
                return uni_char + token[uni_len:]
            #if not uc0 and chars
            else:
                for i in xrange(uni_len, len(token)):
                    if token[i] == " ":
                        continue
                    elif self.__uc_char > 0:
                        self.__uc_char -= 1
                    else:
                        return uni_char + token[i:]
            #print('uc: ' + str(self.__uc_value) + 'uni: ' + str(uni_char) + 'token: ' + token)
        #default
        return token
    
    def __sub_reg_split(self,input_file):
        input_file = self.__replace_spchar.mreplace(input_file)
        #input_file = re.sub(self.__utf_exp, self.__from_ms_to_utf8, input_file)
        # line = re.sub( self.__neg_utf_exp, self.__neg_unicode_func, line)
        # this is for older RTF
        #line = re.sub(self.__par_exp, '\\par ', line)
        input_file = re.sub(self.__ms_hex_exp, "\\mshex0\g<1> ", input_file)
        #split
        tokens = re.split(self.__splitexp, input_file)
        #remove empty tokens and \n
        return filter(lambda x: len(x) > 0 and x != '\n', tokens)
        #return filter(lambda x: len(x) > 0, \
            #(self.__remove_line.sub('', x) for x in tokens))
        
        
    def __compile_expressions(self):
        SIMPLE_RPL = {
            "\\\\": "\\backslash ",
            "\\~": "\\~ ",
            "\\;": "\\; ",
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            "\\~": "\\~ ",
            "\\_": "\\_ ",
            "\\:": "\\: ",
            "\\-": "\\- ",
            # turn into a generic token to eliminate special
            # cases and make processing easier
            "\\{": "\\ob ",
            # turn into a generic token to eliminate special
            # cases and make processing easier
            "\\}": "\\cb ",
            # put a backslash in front of to eliminate special cases and
            # make processing easier
            "{": "\\{",
            # put a backslash in front of to eliminate special cases and
            # make processing easier
            "}": "\\}",
            # this is for older RTF
            r'\\$': '\\par ',
            }
        self.__replace_spchar = MReplace(SIMPLE_RPL)
        self.__ms_hex_exp = re.compile(r"\\\'([0-9a-fA-F]{2})") #r"\\\'(..)"
        self.__utf_exp = re.compile(r"\\u(-?\d{3,6}) {0,1}") #modify this
        #self.__utf_exp = re.compile(r"^\\u(-?\d{3,6})")
        #add \n in split for whole file reading
        #self.__splitexp = re.compile(r"(\\[\\{}]|{|}|\n|\\[^\s\\{}&]+(?:\s)?)")
        #why keep backslash whereas \is replaced before?
        self.__splitexp = re.compile(r"(\\[{}]|\n|\\[^\s\\{}&]+(?:[ \t\r\f\v])?)")
        #self.__par_exp = re.compile(r'\\$')
        #self.__remove_line = re.compile(r'\n+')
        #self.__mixed_exp = re.compile(r"(\\[a-zA-Z]+\d+)(\D+)")
        ##self.num_exp = re.compile(r"(\*|:|[a-zA-Z]+)(.*)")
        
    def tokenize(self):
        """Main class for handling other methods. Reads the file \
        , uses method self.sub_reg to make basic substitutions,\
        and process tokens by itself"""
        #read
        read_obj = open(self.__file, 'r')
        input_file = read_obj.read()
        read_obj.close()
        
        #process simple replacements and split giving us a correct list
        #remove '' and \n in the process
        tokens = self.__sub_reg_split(input_file)
        #correct unicode
        #tokens = map(self.__unicode_process, tokens)
        #remove empty items created by removing \uc
        #tokens = filter(lambda x: len(x) > 0, tokens)
        
        #write
        write_obj = open(self.__write_to, 'wb')
        write_obj.write('\n'.join(tokens))
        write_obj.close()
        #Move and copy
        copy_obj = copy.Copy(bug_handler = self.__bug_handler)
        if self.__copy:
            copy_obj.copy_file(self.__write_to, "tokenize.data")
        copy_obj.rename(self.__write_to, self.__file)
        os.remove(self.__write_to)
        
        #self.__special_tokens = [ '_', '~', "'", '{', '}' ]
        '''line = line.replace("\\\\", "\\backslash ")
        line = line.replace("\\~", "\\~ ")
        line = line.replace("\\;", "\\; ")
        line = line.replace("&", "&amp;")
        line = line.replace("<", "&lt;")
        line = line.replace(">", "&gt;")
        line = line.replace("\\~", "\\~ ")
        line = line.replace("\\_", "\\_ ")
        line = line.replace("\\:", "\\: ")
        line = line.replace("\\-", "\\- ")
        # turn into a generic token to eliminate special
        # cases and make processing easier
        line = line.replace("\\{", "\\ob ")
        # turn into a generic token to eliminate special
        # cases and make processing easier
        line = line.replace("\\}", "\\cb ")
        # put a backslash in front of to eliminate special cases and
        # make processing easier
        line = line.replace("{", "\\{")
        # put a backslash in front of to eliminate special cases and
        # make processing easier
        line = line.replace("}", "\\}")
        
        line_to_read = "dummy"
        while line_to_read:
            line_to_read = read_obj.readline()
            line = line_to_read
            line = line.replace("\n", "")
        '''
        '''if token != "":
                write_obj.write(token + "\n")
                
                match_obj = re.search(self.__mixed_exp, token)
                if match_obj != None:
                    first = match_obj.group(1)
                    second = match_obj.group(2)
                    write_obj.write(first + "\n")
                    write_obj.write(second + "\n")
                else:
                    write_obj.write(token + "\n")
            '''
        '''
        for line in read_obj:
            #make all replacements
            line = self.__sub_reg(line)
            #split token and remove empty tokens
            tokens = filter(lambda x: len(x) > 0,
                re.split(self.__splitexp, line))
            if tokens:
                write_obj.write('\n'.join(tokens)+'\n')'''
                
        '''def __neg_unicode_func(self, match_obj):
        neg_uni_char = int(match_obj.group(1)) * -1
        # sys.stderr.write(str( neg_uni_char))
        uni_char = neg_uni_char + 65536
        return   '&#x' + str('%X' % uni_char) + ';'''