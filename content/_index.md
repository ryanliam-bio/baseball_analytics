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
          <img src="/media/avatar.jpg" style="width: 200px; border-radius: 50%; margin-bottom: 20px;">
          
          <h1 style="margin-top: 0;">Liam Ryan</h1>
          <h3 style="color: #6c757d; margin-top: -10px;">Independent Baseball Researcher</h3>
        </div>

        For better or worse, I love baseball. This site is a reflection of my efforts to further develop my analytical skills and share my thoughts about the game and its players.

        <div style="text-align: center;">

        {{< icon name="envelope" pack="fas" >}} [Email Me](mailto:liam.ryan@comcast.net) | {{< icon name="" pack="fab" >}} [LinkedIn](https://www.linkedin.com/in/liam-r-22912998/)

        </div>
    design:
      columns: '1'
      background:
        gradient_mesh:
          enable: true

  # 2. MISSION STATEMENT
  - block: markdown
    content:
      title: '⚾ My Mission'
      subtitle: 'Bridging the gap between raw Statcast data and actionable insights.'
      text: |-
        I am an independent baseball researcher dedicated to uncovering value in the MLB awards market. By leveraging predictive modeling and advanced sabermetrics, I analyze how player performance translates to hardware.

        My current work focuses on:
        * **Predictive Modeling:** Identifying undervalued MVP and Cy Young candidates.
        * **Statcast Deep Dives:** Identifying breakout candidates using pitch-level metrics.
    design:
      columns: '1'

  # 3. PROJECTS SECTION
  - block: collection
    id: projects
    content:
      title: Featured Analysis
      filters:
        folders:
          - project
    design:
      view: article-grid
      columns: 2

  # 4. HIDE EVERYTHING ELSE
  - block: collection
    id: news
    active: false
  - block: collection
    id: papers
    active: false
  - block: collection
    id: talks
    active: false
  - block: cta-card
    demo: true 
    active: false
---