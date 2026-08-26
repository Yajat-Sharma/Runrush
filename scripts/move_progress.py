import re

with open('templates/index.html', 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Extract the progressSection block
progress_section_match = re.search(r'(<div class="glass p-3 p-md-4 mb-4" id="progressSection">.*?)</div> <!-- /#progressHomeOrigin -->', html, re.DOTALL)
if progress_section_match:
    progress_html = progress_section_match.group(1).strip()
    
    # 2. Remove the progressHomeOrigin and its contents from the Home view
    html = re.sub(r'<!-- PROGRESS GRAPH -->\s*<div id="progressHomeOrigin">.*?</div> <!-- /#progressHomeOrigin -->', '', html, flags=re.DOTALL)
    
    # 3. Insert it into the Analytics view, replacing progressGraphDestination
    html = re.sub(r'<!-- Progress Graph Destination -->\s*<div id="progressGraphDestination"></div>', '<!-- Progress Graph -->\n        ' + progress_html, html)
    
    # 4. Remove the appendChild logic in switchTab
    switch_tab_logic = r'''      // Move components into Analytics view if selected, or back to Home
      const progress = document.getElementById\('progressSection'\);
      
      if \(progress\) \{
        if \(tabId === 'analytics'\) \{
          document.getElementById\('progressGraphDestination'\).appendChild\(progress\);
        \} else if \(tabId === 'home'\) \{
          // Send them back to Home locations
          document.getElementById\('progressHomeOrigin'\).appendChild\(progress\);
        \}
      \}'''
    
    html = re.sub(switch_tab_logic, '', html)
    
    with open('templates/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print('Successfully moved progressSection to Analytics view and cleaned up JS.')
else:
    print('Error: Could not find progressSection in HTML.')
