---
title: 'Projects'
date: 2024-05-19
type: landing

design:
  # Section spacing
  spacing: '5rem'

# Page sections
sections:
  # Featured: whichever pages have `featured: true` in their front matter, lowest weight first.
  - block: collection
    id: featured
    content:
      title: Featured Work
      text: My latest write-ups. Everything else is below, or browse by topic from the Projects menu.
      filters:
        folders:
          - projects
        featured_only: true
      sort_by: 'weight'
      sort_ascending: true
      count: 3
    design:
      view: article-grid
      fill_image: false
      columns: 3
      show_date: true
      show_read_time: false
      show_read_more: false

  - block: collection
    id: all
    content:
      title: All Projects
      text: Research and fantasy-based projects across biomechanics, Bayesian modeling, and Statcast analysis. I am continuously seeking to expand the scope of my work and improve on previous iterations, but please enjoy my currently published writeups.
      filters:
        folders:
          - projects
      sort_by: 'weight'
      sort_ascending: true
      count: 0
      paginate: 20
    design:
      view: article-grid
      fill_image: false
      columns: 2
      show_date: false
      show_read_time: false
      show_read_more: false
---
