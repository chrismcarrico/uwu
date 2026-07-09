# uwu

CLI for scaffolding and building LaTeX homework assignments.

## Install

```sh
uv tool install --editable .
```

## Usage

```sh
# copy the template into ./spce5085/a1/carrico_spce5085_a1.tex
uwu new spce5085/a1

# override the generated filename
uwu new spce5085/a1 -o my_writeup

# scaffold the problem skeletons at creation time too (quotes optional)
uwu new spce5085/a1 4.1, 4.2, 4.4a, 4.8a-b, 4.11i

# build the .tex file in the current directory via docker + pdflatex
uwu build

# build a specific assignment directory, with a custom output name
uwu build spce5085/a1 -o final

# or insert them into an existing assignment later (quotes optional)
uwu problems spce5085/a1 4.1, 4.2, 4.4a, 4.8a-b, 4.11i
```
