---
title: 'Liam Ryan | MLB Analytics'
summary: 'Independent Baseball Researcher specializing in Statcast data and award market prediction.'
date: 2026-01-23
type: landing

design:
  spacing: '6rem'

sections:
  # 1. MANUAL BIOGRAPHY (Bypassing the broken admin folder)
  - block: markdown
    content:
      #title: 'Liam Ryan'
      subtitle: 'Independent Baseball Researcher'
      text: |-
        <div style="display: flex; flex-direction: column; align-items: center; text-align: center;">
          <img src="media/avatar.jpg" style="width: 200px; border-radius: 50%; margin-bottom: 20px;">
          
          <h1 style="margin-top: 0;">Liam Ryan</h1>
          <h3 style="color: #6c757d; margin-top: -10px;">Independent Baseball Researcher</h3>
        </div>
        <div style="text-align: center;">
        I work in biomechanics and performance science, with a professional background supporting force plate measurement systems used in elite sport environments.

        <div>
        <div style="text-align: center;">

        {{< icon name="envelope" pack="fas" >}} [Email Me](mailto:liam.ryan@comcast.net) | {{< icon name="link" pack="fas" >}} [LinkedIn](https://www.linkedin.com/in/liam-r-22912998/)

        </div>
    design:
      columns: '3'
      background:
        gradient_mesh:
          enable: true

  # 2. MISSION STATEMENT
  - block: markdown
    content:
      title: 'Applied Baseball Research'
      subtitle: 'From tracking data to performance questions.'
      text: |-
        I use baseball tracking data to explore questions related to player performance, development, and variability. Much of my work focuses on understanding how observable outcomes (such as release point, swing speed, or batted-ball tendencies) can reflect underlying mechanical or approach-level changes, while recognizing the limitations of proxy data.

        This site serves as a working archive of analyses, written notes, and exploratory research as I continue to build applied performance science skills. Emphasis is placed on clear problem framing, reproducible workflows, and communicating uncertainty alongside results.
    design:
      columns: '1'

  # 3. PROJECTS SECTION
  - block: collection
    id: projects
    content:
      title: Featured Analysis
      filters:
        folders:
          - projects
      sort_by: 'weight'
      sort_ascending: true
      count: 2
      offset: 0
    design:
      view: article-grid
      columns: 2
      

  # 4. HIDE EVERYTHING ELSE
  - block: collection
    id: archive
    active: false
  - block: collection
    id: posts
    active: false
---