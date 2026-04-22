from bs4 import BeautifulSoup

from docs2pdf.crawler import Crawler


def test_extract_content_formatting():
    # Mock root_url and project_name for Crawler init
    crawler = Crawler("http://example.com", "test_project")

    html = """
    <html>
    <body>
    <li>
        <p>Replace</p>
        <pre>SET_RUNNER_NAME_HERE</pre>
        with the name of the available runner or the runner you installed.
        <p>The runner's name is case-sensitive.</p>
    </li>
    <li>
        <p>Click</p>
        <pre>config</pre>
        and open
        <pre>agent_tag.yml</pre>.
    </li>
    <li>
        <p>Follow these steps:</p>
        <pre>line 1\nline 2</pre>
    </li>
    </body>
    </html>
    """

    content = crawler._post_process_content(html)
    soup = BeautifulSoup(content, "html.parser")

    # Check if SET_RUNNER_NAME_HERE is code and unwrapped
    code_set = soup.find(string=lambda t: "SET_RUNNER_NAME_HERE" in t)
    assert code_set is not None
    assert code_set.parent.name == "code"

    # Check if "Replace" is unwrapped (not in p)
    replace_text = soup.find(string=lambda t: "Replace" in t)
    assert replace_text is not None
    # In my test html, Replace is in a p, and it is a sibling of a pre that became code.
    # So it should be unwrapped.
    assert replace_text.parent.name == "li" or replace_text.parent.name == "body"

    # Check if multi-line pre is still pre
    multi_line = soup.find(string=lambda t: "line 1" in t)
    assert multi_line is not None
    assert multi_line.find_parent("pre") is not None


def test_extract_content_mini_toc_removal():
    crawler = Crawler("http://example.com", "test_project")
    html = """
    <html>
    <body>
    <h1>Title</h1>
    <ul>
        <li><a href="#section1">Section 1</a></li>
        <li><a href="#section2">Section 2</a></li>
    </ul>
    <h2 id="section1">Section 1</h2>
    <p>Content 1</p>
    <h2 id="section2">Section 2</h2>
    <p>Content 2</p>
    </body>
    </html>
    """
    content = crawler._post_process_content(html)
    soup = BeautifulSoup(content, "html.parser")
    # The mini-toc should be removed
    assert soup.find("ul") is None
    # h1 should be removed
    assert soup.find("h1") is None
    # h2 and p should stay
    assert soup.find("h2") is not None
    assert soup.find("p") is not None
