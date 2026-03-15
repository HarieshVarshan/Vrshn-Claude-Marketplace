"""
Markdown <-> Confluence XHTML conversion with cfl:// URL scheme support.

Uses mistune for Markdown parsing and html.parser for XHTML->Markdown conversion.

cfl:// URL scheme:
    cfl://user/username          -> User mention
    cfl://page/SPACE/Title       -> Page link
    cfl://date/YYYY-MM-DD        -> Date macro
    cfl://status/Color/Text      -> Status macro
    cfl://jira/KEY-123           -> Jira issue macro
    cfl://image/file.png?w=200   -> Attached image
    cfl://attachment/file.pdf    -> Attachment link
"""

import re
from html.parser import HTMLParser
from typing import Optional

import mistune


# ---------------------------------------------------------------------------
# cfl:// URL pre-processor
# ---------------------------------------------------------------------------

_CFL_LINK_RE = re.compile(
    r'\[(?P<text>[^\]]*)\]\(cfl://(?P<scheme>[^/]+)/(?P<path>[^)]+)\)'
)
_CFL_IMAGE_RE = re.compile(
    r'!\[(?P<alt>[^\]]*)\]\(cfl://image/(?P<path>[^)]+)\)'
)


def _parse_cfl_params(path: str) -> tuple[str, dict[str, str]]:
    """Split 'file.png?width=200&border=true' into ('file.png', {'width': '200', ...})."""
    if '?' in path:
        base, qs = path.split('?', 1)
        params = {}
        for pair in qs.split('&'):
            if '=' in pair:
                k, v = pair.split('=', 1)
                params[k] = v
        return base, params
    return path, {}


def preprocess_cfl_urls(markdown: str) -> str:
    """Convert cfl:// URLs to placeholder XML tags that survive mistune parsing."""

    def _replace_image(m: re.Match) -> str:
        path = m.group('path')
        alt = m.group('alt')
        filename, params = _parse_cfl_params(path)
        width_attr = f' width="{params["width"]}"' if 'width' in params else ''
        if 'w' in params and 'width' not in params:
            width_attr = f' width="{params["w"]}"'
        return f'<cfl-image filename="{filename}" alt="{alt}"{width_attr}/>'

    def _replace_link(m: re.Match) -> str:
        text = m.group('text')
        scheme = m.group('scheme')
        path = m.group('path')

        if scheme == 'user':
            return f'<cfl-user username="{path}">{text}</cfl-user>'
        elif scheme == 'page':
            parts = path.split('/', 1)
            space = parts[0]
            title = parts[1] if len(parts) > 1 else text
            return f'<cfl-page space="{space}" title="{title}">{text}</cfl-page>'
        elif scheme == 'date':
            return f'<cfl-date date="{path}">{text}</cfl-date>'
        elif scheme == 'status':
            parts = path.split('/', 1)
            color = parts[0]
            status_text = parts[1] if len(parts) > 1 else text
            return f'<cfl-status color="{color}" text="{status_text}"/>'
        elif scheme == 'jira':
            return f'<cfl-jira key="{path}"/>'
        elif scheme == 'attachment':
            filename, _ = _parse_cfl_params(path)
            return f'<cfl-attachment filename="{filename}">{text}</cfl-attachment>'
        return m.group(0)

    result = _CFL_IMAGE_RE.sub(_replace_image, markdown)
    result = _CFL_LINK_RE.sub(_replace_link, result)
    return result


# ---------------------------------------------------------------------------
# cfl:// placeholder -> Confluence XHTML expansion
# ---------------------------------------------------------------------------

_CFL_USER_RE = re.compile(
    r'<cfl-user username="([^"]+)">([^<]*)</cfl-user>'
)
_CFL_PAGE_RE = re.compile(
    r'<cfl-page space="([^"]+)" title="([^"]+)">([^<]*)</cfl-page>'
)
_CFL_DATE_RE = re.compile(
    r'<cfl-date date="([^"]+)">([^<]*)</cfl-date>'
)
_CFL_STATUS_RE = re.compile(
    r'<cfl-status color="([^"]+)" text="([^"]+)"/>'
)
_CFL_JIRA_RE = re.compile(
    r'<cfl-jira key="([^"]+)"/>'
)
_CFL_IMAGE_TAG_RE = re.compile(
    r'<cfl-image filename="([^"]+)" alt="([^"]*)"(?:\s+width="([^"]*)")?/>'
)
_CFL_ATTACHMENT_RE = re.compile(
    r'<cfl-attachment filename="([^"]+)">([^<]*)</cfl-attachment>'
)


def _expand_cfl_placeholders(xhtml: str) -> str:
    """Convert placeholder tags to actual Confluence macros."""

    xhtml = _CFL_USER_RE.sub(
        r'<ac:link><ri:user ri:username="\1"/><ac:plain-text-link-body><![CDATA[\2]]></ac:plain-text-link-body></ac:link>',
        xhtml
    )
    xhtml = _CFL_PAGE_RE.sub(
        r'<ac:link><ri:page ri:space-key="\1" ri:content-title="\2"/><ac:plain-text-link-body><![CDATA[\3]]></ac:plain-text-link-body></ac:link>',
        xhtml
    )
    xhtml = _CFL_DATE_RE.sub(
        r'<time datetime="\1"/>',
        xhtml
    )
    xhtml = _CFL_STATUS_RE.sub(
        r'<ac:structured-macro ac:name="status"><ac:parameter ac:name="colour">\1</ac:parameter><ac:parameter ac:name="title">\2</ac:parameter></ac:structured-macro>',
        xhtml
    )
    xhtml = _CFL_JIRA_RE.sub(
        r'<ac:structured-macro ac:name="jira"><ac:parameter ac:name="key">\1</ac:parameter></ac:structured-macro>',
        xhtml
    )

    def _expand_image(m: re.Match) -> str:
        filename = m.group(1)
        width = m.group(3)
        width_param = f'<ac:parameter ac:name="width">{width}</ac:parameter>' if width else ''
        return f'<ac:image>{width_param}<ri:attachment ri:filename="{filename}"/></ac:image>'

    xhtml = _CFL_IMAGE_TAG_RE.sub(_expand_image, xhtml)

    xhtml = _CFL_ATTACHMENT_RE.sub(
        r'<ac:link><ri:attachment ri:filename="\1"/><ac:plain-text-link-body><![CDATA[\2]]></ac:plain-text-link-body></ac:link>',
        xhtml
    )

    return xhtml


# ---------------------------------------------------------------------------
# Mistune custom renderer -> Confluence storage format
# ---------------------------------------------------------------------------

class ConfluenceRenderer(mistune.HTMLRenderer):
    """Renders Markdown AST to Confluence XHTML storage format.

    Extends HTMLRenderer to inherit its render_token() which pre-renders
    children into a `text` string and unpacks attrs as kwargs.
    Method signatures match HTMLRenderer conventions.
    """

    NAME = 'confluence'

    def __init__(self):
        super().__init__(escape=False)

    def text(self, text: str) -> str:
        return text

    def paragraph(self, text: str) -> str:
        return f'<p>{text}</p>\n'

    def heading(self, text: str, level: int, **attrs) -> str:
        return f'<h{level}>{text}</h{level}>\n'

    def thematic_break(self) -> str:
        return '<hr/>\n'

    def block_text(self, text: str) -> str:
        return text

    def block_code(self, code: str, info: Optional[str] = None, **attrs) -> str:
        lang_param = ''
        if info:
            lang = info.split()[0]
            lang_param = f'<ac:parameter ac:name="language">{lang}</ac:parameter>'
        return (
            f'<ac:structured-macro ac:name="code">'
            f'{lang_param}'
            f'<ac:plain-text-body><![CDATA[{code}]]></ac:plain-text-body>'
            f'</ac:structured-macro>\n'
        )

    def block_quote(self, text: str) -> str:
        return (
            f'<ac:structured-macro ac:name="quote">'
            f'<ac:rich-text-body>{text}</ac:rich-text-body>'
            f'</ac:structured-macro>\n'
        )

    def list(self, text: str, ordered: bool, **attrs) -> str:
        tag = 'ol' if ordered else 'ul'
        return f'<{tag}>{text}</{tag}>\n'

    def list_item(self, text: str, **attrs) -> str:
        return f'<li>{text}</li>'

    # -- Table --

    def table(self, text: str) -> str:
        return f'<table><tbody>{text}</tbody></table>\n'

    def table_head(self, text: str) -> str:
        return f'<tr>{text}</tr>'

    def table_body(self, text: str) -> str:
        return text

    def table_row(self, text: str) -> str:
        return f'<tr>{text}</tr>'

    def table_cell(self, text: str, align: Optional[str] = None, head: bool = False, **attrs) -> str:
        tag = 'th' if head else 'td'
        return f'<{tag}>{text}</{tag}>'

    # -- Inline --

    def emphasis(self, text: str) -> str:
        return f'<em>{text}</em>'

    def strong(self, text: str) -> str:
        return f'<strong>{text}</strong>'

    def codespan(self, text: str) -> str:
        return f'<code>{text}</code>'

    def linebreak(self) -> str:
        return '<br/>'

    def softbreak(self) -> str:
        return '\n'

    def link(self, text: str, url: str, title: Optional[str] = None) -> str:
        return f'<a href="{url}">{text}</a>'

    def image(self, text: str, url: str, title: Optional[str] = None) -> str:
        if url.startswith('http://') or url.startswith('https://'):
            return f'<ac:image><ri:url ri:value="{url}"/></ac:image>'
        return f'<ac:image><ri:attachment ri:filename="{url}"/></ac:image>'

    def strikethrough(self, text: str) -> str:
        return f'<span style="text-decoration: line-through;">{text}</span>'

    def inline_html(self, html: str) -> str:
        return html

    def block_html(self, html: str) -> str:
        return html

    def __call__(self, tokens, state):
        out = self.render_tokens(tokens, state)
        return _expand_cfl_placeholders(out)


# ---------------------------------------------------------------------------
# Public API: Markdown -> Confluence XHTML
# ---------------------------------------------------------------------------

_md = mistune.create_markdown(
    renderer=ConfluenceRenderer(),
    plugins=['strikethrough', 'table'],
)


def markdown_to_confluence_xhtml(text: str) -> str:
    """Convert Markdown (with optional cfl:// URLs) to Confluence XHTML storage format."""
    preprocessed = preprocess_cfl_urls(text)
    return _md(preprocessed)


# ---------------------------------------------------------------------------
# Confluence XHTML -> Markdown converter (html.parser based)
# ---------------------------------------------------------------------------

class ConfluenceXHTMLToMarkdown(HTMLParser):
    """Converts Confluence XHTML storage format to Markdown."""

    def __init__(self):
        super().__init__()
        self._output: list[str] = []
        self._tag_stack: list[str] = []
        self._attrs_stack: list[dict] = []
        self._list_stack: list[str] = []
        self._list_counter: list[int] = []
        self._table_row: list[str] = []
        self._table_rows: list[list[str]] = []
        self._in_table_head = False
        self._in_code_macro = False
        self._code_language = ''
        self._in_quote_macro = False
        self._macro_stack: list[str] = []
        self._macro_params: dict[str, str] = {}
        self._skip_content = False
        self._buf = ''

    def _current_tag(self) -> str:
        return self._tag_stack[-1] if self._tag_stack else ''

    def _attrs_dict(self, attrs: list) -> dict:
        return {k: v for k, v in attrs}

    def handle_starttag(self, tag: str, attrs: list):
        ad = self._attrs_dict(attrs)
        self._tag_stack.append(tag)
        self._attrs_stack.append(ad)

        if tag in ('strong', 'b'):
            self._output.append('**')
        elif tag in ('em', 'i'):
            self._output.append('*')
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            level = int(tag[1])
            self._output.append('\n' + '#' * level + ' ')
        elif tag == 'p':
            if self._in_quote_macro:
                self._output.append('> ')
        elif tag == 'br':
            self._output.append('  \n')
        elif tag == 'hr':
            self._output.append('\n---\n')
        elif tag == 'code':
            if not self._in_code_macro:
                self._output.append('`')
        elif tag == 'a':
            self._buf = ''
        elif tag == 'img':
            src = ad.get('src', '')
            alt = ad.get('alt', '')
            self._output.append(f'![{alt}]({src})')
        elif tag == 'ul':
            self._list_stack.append('ul')
            self._list_counter.append(0)
        elif tag == 'ol':
            self._list_stack.append('ol')
            self._list_counter.append(0)
        elif tag == 'li':
            depth = len(self._list_stack) - 1
            indent = '  ' * depth
            if self._list_stack and self._list_stack[-1] == 'ol':
                self._list_counter[-1] += 1
                self._output.append(f'\n{indent}{self._list_counter[-1]}. ')
            else:
                self._output.append(f'\n{indent}- ')
        elif tag == 'table':
            self._table_rows = []
            self._in_table_head = False
        elif tag == 'th':
            self._buf = ''
            self._in_table_head = True
        elif tag == 'td':
            self._buf = ''
        elif tag == 'tr':
            self._table_row = []
        elif tag == 'ac:structured-macro':
            macro_name = ad.get('ac:name', '')
            self._macro_stack.append(macro_name)
            self._macro_params = {}
            if macro_name == 'code':
                self._in_code_macro = True
                self._code_language = ''
            elif macro_name == 'quote':
                self._in_quote_macro = True
        elif tag == 'ac:parameter':
            self._buf = ''
        elif tag == 'ac:plain-text-body':
            self._buf = ''
        elif tag == 'ac:rich-text-body':
            pass
        elif tag == 'ac:image':
            self._buf = ''
            self._macro_params = {}
        elif tag == 'ri:attachment':
            self._macro_params['attachment'] = ad.get('ri:filename', '')
        elif tag == 'ri:url':
            self._macro_params['url'] = ad.get('ri:value', '')
        elif tag == 'ri:user':
            self._macro_params['user'] = ad.get('ri:username', '')
        elif tag == 'ri:page':
            self._macro_params['page_space'] = ad.get('ri:space-key', '')
            self._macro_params['page_title'] = ad.get('ri:content-title', '')
        elif tag == 'ac:link':
            self._buf = ''
            self._macro_params = {}
        elif tag == 'time':
            dt = ad.get('datetime', '')
            self._output.append(f'[{dt}](cfl://date/{dt})')
            self._skip_content = True

    def handle_endtag(self, tag: str):
        if self._tag_stack and self._tag_stack[-1] == tag:
            self._tag_stack.pop()
            self._attrs_stack.pop()

        if tag in ('strong', 'b'):
            self._output.append('**')
        elif tag in ('em', 'i'):
            self._output.append('*')
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self._output.append('\n')
        elif tag == 'p':
            self._output.append('\n\n')
        elif tag == 'code':
            if not self._in_code_macro:
                self._output.append('`')
        elif tag == 'a':
            href = ''
            for i in range(len(self._attrs_stack) - 1, -1, -1):
                if 'href' in self._attrs_stack[i]:
                    href = self._attrs_stack[i]['href']
                    break
            text = self._buf or href
            if href:
                self._output.append(f'[{text}]({href})')
            else:
                self._output.append(text)
            self._buf = ''
        elif tag in ('ul', 'ol'):
            if self._list_stack:
                self._list_stack.pop()
                self._list_counter.pop()
            self._output.append('\n')
        elif tag in ('th', 'td'):
            self._table_row.append(self._buf.strip())
            self._buf = ''
        elif tag == 'tr':
            self._table_rows.append(self._table_row)
            self._table_row = []
            if self._in_table_head:
                self._in_table_head = False
        elif tag == 'table':
            self._render_table()
        elif tag == 'ac:parameter':
            if self._macro_stack:
                macro = self._macro_stack[-1]
                if macro == 'code' and self._buf:
                    self._code_language = self._buf.strip()
            param_name = ''
            for i in range(len(self._attrs_stack) - 1, -1, -1):
                if 'ac:name' in self._attrs_stack[i]:
                    param_name = self._attrs_stack[i]['ac:name']
                    break
            if param_name:
                self._macro_params[param_name] = self._buf.strip()
            self._buf = ''
        elif tag == 'ac:plain-text-body':
            pass
        elif tag == 'ac:structured-macro':
            if self._macro_stack:
                macro = self._macro_stack.pop()
                if macro == 'code':
                    lang = self._code_language
                    code = self._buf.strip()
                    self._output.append(f'\n```{lang}\n{code}\n```\n')
                    self._in_code_macro = False
                    self._code_language = ''
                    self._buf = ''
                elif macro == 'quote':
                    self._in_quote_macro = False
                elif macro == 'status':
                    color = self._macro_params.get('colour', 'Grey')
                    title = self._macro_params.get('title', '')
                    self._output.append(f'[{title}](cfl://status/{color}/{title})')
                elif macro == 'jira':
                    key = self._macro_params.get('key', '')
                    self._output.append(f'[{key}](cfl://jira/{key})')
                else:
                    self._output.append(f'<!-- confluence:{macro} -->')
                self._macro_params = {}
        elif tag == 'ac:image':
            attachment = self._macro_params.get('attachment', '')
            url = self._macro_params.get('url', '')
            width = self._macro_params.get('width', '')
            if attachment:
                width_param = f'?width={width}' if width else ''
                self._output.append(f'![{attachment}](cfl://image/{attachment}{width_param})')
            elif url:
                self._output.append(f'![]({url})')
            self._macro_params = {}
        elif tag == 'ac:link':
            user = self._macro_params.get('user', '')
            page_space = self._macro_params.get('page_space', '')
            page_title = self._macro_params.get('page_title', '')
            attachment = self._macro_params.get('attachment', '')
            text = self._buf.strip()

            if user:
                display = text or user
                self._output.append(f'[{display}](cfl://user/{user})')
            elif page_space and page_title:
                display = text or page_title
                self._output.append(f'[{display}](cfl://page/{page_space}/{page_title})')
            elif attachment:
                display = text or attachment
                self._output.append(f'[{display}](cfl://attachment/{attachment})')
            self._buf = ''
            self._macro_params = {}
        elif tag == 'time':
            self._skip_content = False

    def handle_data(self, data: str):
        if self._skip_content:
            return
        current = self._current_tag()
        if current in ('a', 'th', 'td', 'ac:parameter', 'ac:plain-text-body',
                        'ac:plain-text-link-body'):
            self._buf += data
            return
        if self._in_code_macro:
            self._buf += data
            return
        self._output.append(data)

    def handle_comment(self, data: str):
        pass

    def _render_table(self):
        if not self._table_rows:
            return
        self._output.append('\n')
        for i, row in enumerate(self._table_rows):
            self._output.append('| ' + ' | '.join(row) + ' |\n')
            if i == 0:
                self._output.append('| ' + ' | '.join('---' for _ in row) + ' |\n')
        self._output.append('\n')
        self._table_rows = []

    def get_markdown(self) -> str:
        result = ''.join(self._output)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()


def confluence_xhtml_to_markdown(xhtml: str) -> str:
    """Convert Confluence XHTML storage format to Markdown with cfl:// URLs."""
    parser = ConfluenceXHTMLToMarkdown()
    parser.feed(xhtml)
    return parser.get_markdown()


# ---------------------------------------------------------------------------
# Content detection heuristic
# ---------------------------------------------------------------------------

_XHTML_START_RE = re.compile(
    r'^\s*<(?:p|h[1-6]|div|table|ul|ol|ac:|ri:)',
    re.IGNORECASE
)


def is_xhtml_content(content: str) -> bool:
    """Heuristic: returns True if content looks like XHTML/Confluence storage format."""
    if not content or not content.strip():
        return False
    return bool(_XHTML_START_RE.match(content.strip()))
