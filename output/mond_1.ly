\version "2.26.0"

\paper {
  indent = 0\mm
  line-width = 180\mm
}

\header {
  tagline = ##f
}

staffA = {
  \clef treble
  \time 4/4
  \set fingeringOrientations = #'(up)
  \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { r8 cis'8-2 e'8-4 } \tuplet 3/2 { r8 cis'8-1 e'8-4 } \tuplet 3/2 { r8 cis'8-2 e'8-5 } |
    \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { r8 cis'8-2 e'8-4 } \tuplet 3/2 { r8 cis'8-1 e'8-2 } \tuplet 3/2 { r8 cis'8-1 e'8-3 } |
    \tuplet 3/2 { a8-1 cis'8-2 e'8-4 } \tuplet 3/2 { r8 cis'8-1 e'8-3 } \tuplet 3/2 { a8-1 d'8-2 fis'8-4 } \tuplet 3/2 { r8 d'8-1 fis'8-3 } |
    \tuplet 3/2 { gis8-1 c'8-2 fis'8-5 } \tuplet 3/2 { r8 cis'8-2 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 dis'8-4 } \tuplet 3/2 { r8 c'8-1 dis'8-2 } |
    \tuplet 3/2 { e8-2 gis8-4 cis'8-5 } \tuplet 3/2 { gis8-2 cis'8-3 e'8-5 } \tuplet 3/2 { gis8-2 cis'8-5 e'8-1 } \tuplet 3/2 { gis'4-2 e'32-1 } gis'16-3 |
    \tuplet 3/2 { gis'8-4 dis'8-2 fis'8-3 } \tuplet 3/2 { r8 dis'8-2 fis'8-3 } \tuplet 3/2 { r8 dis'8-2 fis'8-3 } \tuplet 3/2 { gis'8-5 dis'8-2 fis'32-3 } gis'16-4 |
    \tuplet 3/2 { gis'8-4 cis'8-1 e'8-2 } \tuplet 3/2 { r8 cis'8-1 e'8-2 } \tuplet 3/2 { a'8-5 cis'8-1 fis'8-3 } \tuplet 3/2 { r8 cis'8-1 fis'8-3 } |
    \tuplet 3/2 { gis'8-4 b8-1 e'8-2 } \tuplet 3/2 { r8 b8-1 e'8-2 } \tuplet 3/2 { fis'8-3 b8-1 dis'8-2 } \tuplet 3/2 { b'4-5 dis'8-2 } |
    \tuplet 3/2 { e'8-3 b8-1 e'8-2 } \tuplet 3/2 { r8 b8-1 e'8-2 } \tuplet 3/2 { r8 b8-1 e'8-2 } \tuplet 3/2 { r8 b8-1 e'8-4 } |
    \tuplet 3/2 { g8-1 b8-2 e'8-4 } \tuplet 3/2 { r8 b8-1 e'8-2 } \tuplet 3/2 { r8 b8-1 e'8-2 } \tuplet 3/2 { g'8-3 b8-1 e'32-2 } g'16-3 |
    \tuplet 3/2 { g'8-4 b8-1 f'8-2 } \tuplet 3/2 { r8 b8-1 f'8-2 } \tuplet 3/2 { r8 b8-1 f'8-2 } \tuplet 3/2 { g'8-3 b8-1 f'32-2 } g'16-3 |
    \tuplet 3/2 { g'8-4 c'8-1 e'8-5 } \tuplet 3/2 { g8-1 b8-2 e'8-5 } \tuplet 3/2 { g8-1 cis'8-2 e'8-3 } \tuplet 3/2 { fis'8-4 cis'8-1 e'8-2 } |
    \tuplet 3/2 { fis'8-3 b8-1 d'8-2 } \tuplet 3/2 { r8 b8-1 d'8-2 } \tuplet 3/2 { g'8-4 b8-1 cis'8-2 } \tuplet 3/2 { e'8-4 b8-1 cis'8-2 } |
    \tuplet 3/2 { fis'8-5 b8-1 d'8-2 } \tuplet 3/2 { r8 b8-1 d'8-2 } \tuplet 3/2 { fis'8-4 ais8-1 cis'8-3 } \tuplet 3/2 { r8 ais8-2 cis'8-3 } |
    \tuplet 3/2 { b8-1 d'8-2 fis'8-4 } \tuplet 3/2 { b8-1 d'8-2 fis'8-4 } \tuplet 3/2 { b8-1 dis'8-2 fis'8-3 } \tuplet 3/2 { b'8-5 dis'8-1 fis'8-2 } |
    \tuplet 3/2 { c''8-5 e'8-1 g'8-2 } \tuplet 3/2 { e'8-1 e'8-2 g'8-3 } \tuplet 3/2 { b8-1 e'8-2 g'8-3 } \tuplet 3/2 { b'8-5 e'8-1 g'8-2 } |
    \tuplet 3/2 { b'8-5 dis'8-2 fis'8-3 } \tuplet 3/2 { r8 dis'8-2 fis'8-3 } \tuplet 3/2 { r8 dis'8-2 fis'8-3 } \tuplet 3/2 { b'8-5 dis'8-1 fis'8-2 } |
    \tuplet 3/2 { c''8-5 e'8-1 g'8-2 } \tuplet 3/2 { e'8-1 e'8-2 g'8-3 } \tuplet 3/2 { b8-1 e'8-2 g'8-3 } \tuplet 3/2 { ais'8-5 e'8-1 g'8-2 } |
    \tuplet 3/2 { b'8-5 dis'8-2 fis'8-3 } \tuplet 3/2 { r8 dis'8-2 fis'8-3 } \tuplet 3/2 { b'8-5 d'8-1 f'8-2 } \tuplet 3/2 { r8 d'8-1 f'8-2 } |
    \tuplet 3/2 { b'8-5 cis'8-1 gis'8-4 } \tuplet 3/2 { r8 cis'8-1 gis'8-4 } \tuplet 3/2 { a'8-5 cis'8-1 fis'8-3 } \tuplet 3/2 { r8 cis'8-1 fis'8-3 } |
    \tuplet 3/2 { g'8-4 b8-1 d'8-2 } \tuplet 3/2 { r8 b8-1 d'8-2 } \tuplet 3/2 { fis'8-4 a8-1 dis'8-2 } \tuplet 3/2 { r8 a8-1 dis'8-5 } |
    \tuplet 3/2 { cis'8-3 fis8-1 a8-2 } \tuplet 3/2 { r8 fis8-1 a8-2 } \tuplet 3/2 { cis'8-4 fis8-1 r8 } \tuplet 3/2 { cis'4-5 gis8-2 } |
    \tuplet 3/2 { fis8-1 a8-2 cis'8-4 } \tuplet 3/2 { r8 cis'8-2 fis'8-5 } \tuplet 3/2 { r8 fis'8-1 a'8-2 } \tuplet 3/2 { cis''8-4 fis'8-1 a'32-2 } cis''16-4 |
    \tuplet 3/2 { cis''8-5 gis'8-2 b'8-4 } \tuplet 3/2 { r8 gis'8-1 b'8-2 } \tuplet 3/2 { r8 gis'8-1 b'8-2 } \tuplet 3/2 { cis''8-3 gis'8-1 b'32-2 } cis''16-3 |
    \tuplet 3/2 { cis''8-4 fis'8-1 a'8-2 } \tuplet 3/2 { r8 fis'8-1 a'8-2 } \tuplet 3/2 { c''8-4 fis'8-1 a'8-2 } \tuplet 3/2 { cis''8-4 fis'8-1 a'8-2 } |
    \tuplet 3/2 { dis''8-5 fis'8-1 gis'8-3 } \tuplet 3/2 { r8 fis'8-2 gis'8-3 } \tuplet 3/2 { r8 fis'8-2 gis'8-3 } \tuplet 3/2 { dis''8-4 fis'8-1 gis'8-2 } |
    \tuplet 3/2 { e''8-5 gis'8-1 cis''8-3 } \tuplet 3/2 { r8 gis'8-1 cis''8-3 } \tuplet 3/2 { dis''8-4 fis'8-1 a'8-2 } \tuplet 3/2 { cis''8-4 e'8-1 ais'8-2 } |
    \tuplet 3/2 { c''8-3 c'8-1 dis'8-2 } \tuplet 3/2 { gis'4-5 dis'8-2 } \tuplet 3/2 { a'4-5 dis'8-2 } \tuplet 3/2 { fis'4-3 dis'8-2 } |
    \tuplet 3/2 { r8 c'8-1 dis'8-2 } \tuplet 3/2 { r8 c'8-1 dis'8-2 } \tuplet 3/2 { r8 c'8-1 dis'8-2 } \tuplet 3/2 { r8 c'8-1 dis'8-2 } |
    \tuplet 3/2 { e8-2 e'8-1 gis'8-2 } \tuplet 3/2 { cis''8-5 e'8-1 gis'8-2 } \tuplet 3/2 { e''8-5 e'8-1 gis'8-2 } \tuplet 3/2 { cis''8-5 e'8-1 gis'8-2 } |
    \tuplet 3/2 { r8 e8-1 gis8-2 } \tuplet 3/2 { cis'4-5 gis8-2 } \tuplet 3/2 { e'4-5 gis8-2 } \tuplet 3/2 { cis'4-5 gis8-2 } |
    \tuplet 3/2 { dis8-1 a8-4 fis8-1 } \tuplet 3/2 { c'8-4 a8-1 dis'8-2 } \tuplet 3/2 { c'8-1 fis'8-3 dis'8-2 } \tuplet 3/2 { a'8-5 fis'8-2 c''8-5 } |
    \tuplet 3/2 { e8-1 cis'8-5 gis8-2 } \tuplet 3/2 { e'8-5 cis'8-1 gis'8-4 } \tuplet 3/2 { e'8-1 cis''8-5 gis'8-2 } \tuplet 3/2 { e''8-5 cis''8-3 gis'8-2 } |
    \tuplet 3/2 { cis'8-1 g'8-4 e'8-1 } \tuplet 3/2 { ais'8-2 g'8-1 cis''8-2 } \tuplet 3/2 { ais'8-1 e''8-4 cis''8-1 } \tuplet 3/2 { g''8-4 e''8-1 ais''8-2 } |
    \tuplet 3/2 { fis'8-1 c''8-4 a'8-1 } \tuplet 3/2 { dis''8-2 c''8-1 fis''8-2 } \tuplet 3/2 { dis''8-1 a''8-4 fis''8-1 } \tuplet 3/2 { c'''8-4 a''8-1 dis'''8-4 } |
    \tuplet 3/2 { c'''8-2 fis''8-1 a''8-4 } \tuplet 3/2 { dis''8-1 fis''8-2 c''8-1 } \tuplet 3/2 { dis''8-2 a'8-1 c''8-4 } \tuplet 3/2 { fis'8-1 a'8-4 dis'8-1 } |
    \tuplet 3/2 { fis'8-2 c'8-1 dis'8-2 } \tuplet 3/2 { a8-1 c'8-4 fis8-1 } \tuplet 3/2 { a8-4 r8 fis8-2 } \tuplet 3/2 { r8 fis8-3 a8-5 } |
    \tuplet 3/2 { c8-1 fis8-2 gis8-3 } \tuplet 3/2 { a8-4 gis8-3 fis8-2 } \tuplet 3/2 { r8 fis8-3 a8-5 } \tuplet 3/2 { r8 fis8-2 a8-4 } |
    \tuplet 3/2 { c8-1 fis8-2 gis8-3 } \tuplet 3/2 { a8-4 gis8-3 fis8-2 } \tuplet 3/2 { r8 fis8-3 a8-5 } \tuplet 3/2 { r8 fis8-2 a8-4 } |
    \tuplet 3/2 { c8-1 fis8-2 gis8-3 } \tuplet 3/2 { a8-5 gis8-4 fis8-3 } \tuplet 3/2 { cis8-1 e8-2 cis'8-5 } \tuplet 3/2 { r8 e8-1 cis'8-5 } |
    \tuplet 3/2 { dis8-1 a8-2 cis'8-4 } \tuplet 3/2 { r8 a8-1 cis'8-3 } \tuplet 3/2 { dis8-1 gis8-3 c'8-5 } \tuplet 3/2 { r8 fis8-1 c'8-4 } |
    \tuplet 3/2 { e8-1 gis8-2 cis'8-5 } \tuplet 3/2 { r8 cis'8-2 e'8-4 } \tuplet 3/2 { r8 cis'8-1 e'8-2 } \tuplet 3/2 { gis'8-4 cis'8-1 e'32-2 } gis'16-4 |
    \tuplet 3/2 { gis'8-5 dis'8-2 fis'8-3 } \tuplet 3/2 { r8 dis'8-2 fis'8-3 } \tuplet 3/2 { r8 dis'8-2 fis'8-3 } \tuplet 3/2 { gis'8-5 dis'8-2 fis'32-3 } gis'16-4 |
    \tuplet 3/2 { gis'8-4 cis'8-1 e'8-2 } \tuplet 3/2 { r8 cis'8-1 e'8-2 } \tuplet 3/2 { a'8-5 cis'8-1 fis'8-3 } \tuplet 3/2 { r8 cis'8-1 fis'8-3 } |
    \tuplet 3/2 { gis'8-4 b8-1 e'8-2 } \tuplet 3/2 { r8 b8-1 e'8-2 } \tuplet 3/2 { a'8-4 b8-1 dis'8-2 } \tuplet 3/2 { b'4-5 dis'8-2 } |
    \tuplet 3/2 { e'8-3 b8-1 e'8-2 } \tuplet 3/2 { r8 e'8-1 gis'8-2 } \tuplet 3/2 { r8 e'8-1 gis'8-2 } \tuplet 3/2 { b'8-4 e'8-1 gis'32-2 } b'16-4 |
    \tuplet 3/2 { b'8-5 fis'8-2 a'8-4 } \tuplet 3/2 { r8 fis'8-1 a'8-2 } \tuplet 3/2 { r8 fis'8-1 a'8-2 } \tuplet 3/2 { b'8-3 fis'8-1 a'32-2 } b'16-3 |
    \tuplet 3/2 { b'8-4 e'8-1 gis'8-2 } \tuplet 3/2 { r8 e'8-1 gis'8-2 } \tuplet 3/2 { c''8-4 fis'8-1 gis'8-2 } \tuplet 3/2 { cis''8-5 e'8-1 gis'8-2 } |
    \tuplet 3/2 { dis''8-5 fis'8-1 gis'8-2 } \tuplet 3/2 { r8 fis'8-1 gis'8-2 } \tuplet 3/2 { e''8-5 gis'8-1 cis''8-3 } \tuplet 3/2 { r8 gis'8-1 cis''8-3 } |
    \tuplet 3/2 { d''8-5 fis'8-1 a'8-2 } \tuplet 3/2 { r8 fis'8-1 a'8-3 } \tuplet 3/2 { c''8-5 fis'8-2 gis'8-3 } \tuplet 3/2 { r8 fis'8-2 gis'8-3 } |
    \tuplet 3/2 { cis''8-4 e'8-1 gis'8-2 } \tuplet 3/2 { r8 e'8-1 gis'8-2 } \tuplet 3/2 { r8 f'8-1 gis'8-2 } \tuplet 3/2 { cis''8-5 f'8-1 gis'8-2 } |
    \tuplet 3/2 { d''8-5 fis'8-1 a'8-4 } \tuplet 3/2 { fis'8-2 fis'8-1 a'8-3 } \tuplet 3/2 { cis'8-2 fis'8-1 a'8-2 } \tuplet 3/2 { cis''8-4 fis'8-1 a'8-2 } |
    \tuplet 3/2 { cis''8-4 f'8-1 gis'8-2 } \tuplet 3/2 { r8 f'8-1 gis'8-2 } \tuplet 3/2 { r8 f'8-1 gis'8-2 } \tuplet 3/2 { cis''8-5 f'8-1 gis'8-2 } |
    \tuplet 3/2 { d''8-5 fis'8-1 a'8-4 } \tuplet 3/2 { fis'8-2 fis'8-1 a'8-3 } \tuplet 3/2 { cis'8-1 fis'8-2 a'8-4 } \tuplet 3/2 { c''8-5 fis'8-1 a'8-2 } |
    \tuplet 3/2 { cis''8-4 f'8-1 gis'8-2 } \tuplet 3/2 { r8 f'8-1 gis'8-2 } \tuplet 3/2 { cis''8-5 fis'8-1 a'8-2 } \tuplet 3/2 { r8 fis'8-1 a'8-2 } |
    \tuplet 3/2 { b'8-3 fis'8-1 a'8-2 } \tuplet 3/2 { r8 fis'8-1 a'8-2 } \tuplet 3/2 { r8 fis'8-1 a'8-2 } \tuplet 3/2 { b'8-3 e'8-1 gis'8-2 } |
    \tuplet 3/2 { a'8-4 e'8-1 gis'8-3 } \tuplet 3/2 { a'8-5 dis'8-2 fis'8-3 } \tuplet 3/2 { gis'8-5 dis'8-2 fis'8-3 } \tuplet 3/2 { gis'8-4 cis'8-1 e'8-2 } |
    \tuplet 3/2 { fis'8-4 cis'8-2 dis'8-3 } \tuplet 3/2 { r8 cis'8-2 dis'8-3 } \tuplet 3/2 { gis'8-4 cis'8-1 dis'8-2 } \tuplet 3/2 { a'8-5 cis'8-1 dis'8-2 } |
    \tuplet 3/2 { gis'8-5 cis'8-1 e'8-2 } \tuplet 3/2 { r8 cis'8-1 e'8-2 } \tuplet 3/2 { gis'8-4 c'8-1 dis'8-2 } \tuplet 3/2 { r8 c'8-1 dis'8-3 } |
    \tuplet 3/2 { gis8-1 gis8-2 cis'8-5 } \tuplet 3/2 { r8 cis'8-2 e'8-4 } \tuplet 3/2 { r8 cis'8-2 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } |
    \tuplet 3/2 { gis8-1 dis'8-3 fis'8-4 } \tuplet 3/2 { r8 dis'8-2 fis'8-4 } \tuplet 3/2 { r8 dis'8-3 fis'8-5 } \tuplet 3/2 { gis8-1 dis'8-3 fis'8-5 } |
    \tuplet 3/2 { gis8-1 e'8-3 cis'8-1 } \tuplet 3/2 { gis'8-4 e'8-1 cis''8-5 } \tuplet 3/2 { gis'8-2 e''8-5 cis''8-2 } \tuplet 3/2 { gis''8-5 e''8-3 cis''8-2 } |
    \tuplet 3/2 { c''8-1 dis''8-2 a'8-1 } \tuplet 3/2 { c''8-4 fis'8-1 a'8-4 } \tuplet 3/2 { dis'8-1 fis'8-3 a8-1 } \tuplet 3/2 { c'8-4 gis8-2 r8 } |
    \tuplet 3/2 { <e-1 cis'-4>8 e'8-2 cis'8-1 } \tuplet 3/2 { gis'8-4 e'8-1 cis''8-5 } \tuplet 3/2 { gis'8-2 e''8-5 cis''8-2 } \tuplet 3/2 { gis''8-5 e''8-3 cis''8-2 } |
    \tuplet 3/2 { c''8-1 dis''8-2 a'8-1 } \tuplet 3/2 { c''8-4 fis'8-1 a'8-4 } \tuplet 3/2 { dis'8-1 fis'8-3 a8-1 } \tuplet 3/2 { c'8-5 gis8-3 fis8-2 } |
    \tuplet 3/2 { <e-1 cis'-4>8 gis8-2 cis'8-3 } \tuplet 3/2 { e'8-5 cis'8-3 gis8-2 } \tuplet 3/2 { r8 e8-1 gis8-2 } \tuplet 3/2 { cis'8-5 gis8-2 e8-1 } |
    r8 r32 e16.-2 \tuplet 3/2 { gis8-4 r8 cis8-1 } \tuplet 3/2 { r8 cis8-5 r4 } \tuplet 3/2 { gis,8-2 r8 } |
    r2 <cis-1 e-2 gis-3 cis'-5>2 |
    <cis-1 e-2 gis-3 cis'-5>1
}

staffB = {
  \clef bass
  \time 4/4
  \set fingeringOrientations = #'(down)
  cis,4-1 \tuplet 3/2 { gis8-2 r4 } \tuplet 3/2 { gis8-3 r4 } \tuplet 3/2 { gis8-4 r4 } |
    b,,4-1 \tuplet 3/2 { gis8-2 r4 } \tuplet 3/2 { gis8-3 r4 } \tuplet 3/2 { gis8-4 r4 } |
    a,,4-1 \tuplet 3/2 { a8-2 r4 } fis,,4-1 \tuplet 3/2 { a8-2 r4 } |
    gis,,4-1 \tuplet 3/2 { gis8-2 r4 } gis,,4-1 \tuplet 3/2 { fis8-2 r4 } |
    cis,2.-1 \tuplet 3/2 { gis8-5 cis'8-2 r8 } |
    c,4-1 \tuplet 3/2 { gis8-2 r4 } \tuplet 3/2 { gis8-3 r4 } \tuplet 3/2 { gis8-4 r4 } |
    cis,4-1 \tuplet 3/2 { gis8-2 r4 } fis,,4-1 \tuplet 3/2 { a8-2 r4 } |
    b,,4-1 \tuplet 3/2 { gis8-2 r4 } b,,4-1 \tuplet 3/2 { a8-3 b8-2 r8 } |
    e,4-1 \tuplet 3/2 { gis8-2 r4 } \tuplet 3/2 { gis8-3 r4 } \tuplet 3/2 { gis8-4 r4 } |
    e,4-4 \tuplet 3/2 { g8-1 r4 } \tuplet 3/2 { g8-2 r4 } \tuplet 3/2 { g8-3 r4 } |
    d,4-4 \tuplet 3/2 { g8-1 r4 } \tuplet 3/2 { g8-2 r4 } \tuplet 3/2 { g8-3 r4 } |
    c,4-1 b,,4-2 ais,,4-3 \tuplet 3/2 { fis8-2 r4 } |
    b,,4-1 \tuplet 3/2 { fis8-2 r4 } e,4-2 g,4-1 |
    fis,4-3 \tuplet 3/2 { fis8-2 r4 } fis,,4-1 \tuplet 3/2 { fis8-2 r4 } |
    b,,2.-3 \tuplet 3/2 { b8-1 r4 } |
    \tuplet 3/2 { b8-2 r4 } e,4-2 g,4-1 e,4-2 |
    b,,4-5 \tuplet 3/2 { b8-1 r4 } \tuplet 3/2 { b8-2 r4 } \tuplet 3/2 { b8-3 r4 } |
    \tuplet 3/2 { b8-4 r4 } e,4-2 g,4-1 e,4-2 |
    b,,4-4 \tuplet 3/2 { b8-2 r4 } gis,,4-1 \tuplet 3/2 { b8-2 r4 } |
    f,,4-1 \tuplet 3/2 { b8-2 r4 } fis,,4-1 \tuplet 3/2 { a8-2 r4 } |
    b,,4-1 \tuplet 3/2 { g8-2 r4 } c,4-1 \tuplet 3/2 { fis8-2 r4 } |
    cis,4-1 \tuplet 3/2 { cis8-2 r4 } \tuplet 3/2 { cis,4-3 gis8-1 } \tuplet 3/2 { cis8-4 f8-2 r8 } |
    fis,,4-1 \tuplet 3/2 { a8-4 r4 } \tuplet 3/2 { cis'8-2 r4 } \tuplet 3/2 { cis'8-3 r4 } |
    f,4-1 \tuplet 3/2 { cis'8-2 r4 } \tuplet 3/2 { cis'8-3 r4 } \tuplet 3/2 { cis'8-4 r4 } |
    fis,4-1 \tuplet 3/2 { cis'8-2 r4 } dis,4-2 cis,4-3 |
    c,4-4 \tuplet 3/2 { dis'8-2 r4 } \tuplet 3/2 { dis'8-3 r4 } c,4-4 |
    cis,4-3 \tuplet 3/2 { e'8-2 r4 } fis,,4-4 g,,4-3 |
    \tuplet 3/2 { gis,,2-2 } \tuplet 3/2 { c'8-1 r4 } \tuplet 3/2 { c'8-3 r4 } \tuplet 3/2 { c'8-4 r8 } |
    <gis,-1 gis,,-5>4 gis4-3 a4-2 fis4-4 |
    gis,,1-1 |
    \tuplet 3/2 { <gis,-1 gis,,-5>2 } \tuplet 3/2 { e8-2 r4 } \tuplet 3/2 { e8-3 r4 } \tuplet 3/2 { e8-4 r8 } |
    gis,,1-1 |
    gis,,1-2 |
    gis,,1-3 |
    gis,,1-4~ |
    gis,,1~ |
    \tuplet 3/2 { gis,,2.. } \tuplet 3/2 { dis4-2 } cis4-3 |
    gis,,2-1 dis4-2 cis4-3 |
    gis,,2-3 d4-1 cis4-2 |
    gis,,2-2 a,,4-1 \tuplet 3/2 { cis8-2 r4 } |
    fis,,4-1 \tuplet 3/2 { dis8-2 r4 } gis,,4-2 \tuplet 3/2 { dis8-1 r4 } |
    <gis,-2 cis,-5>4 \tuplet 3/2 { gis8-3 r4 } \tuplet 3/2 { gis8-4 r4 } \tuplet 3/2 { gis8-3 r4 } |
    c,4-1 \tuplet 3/2 { gis8-2 r4 } \tuplet 3/2 { gis8-3 r4 } \tuplet 3/2 { gis8-4 r4 } |
    cis,4-1 \tuplet 3/2 { gis8-2 r4 } fis,,4-1 \tuplet 3/2 { a8-2 r4 } |
    b,,4-1 \tuplet 3/2 { gis8-2 r4 } b,,4-1 \tuplet 3/2 { a8-3 b8-2 r8 } |
    e,4-4 \tuplet 3/2 { b8-1 r4 } \tuplet 3/2 { b8-2 r4 } \tuplet 3/2 { b8-3 r4 } |
    dis,4-4 \tuplet 3/2 { b8-1 r4 } \tuplet 3/2 { b8-2 r4 } \tuplet 3/2 { b8-3 r4 } |
    e,4-1 \tuplet 3/2 { b8-2 r4 } dis,4-2 cis,4-3 |
    c,4-4 \tuplet 3/2 { dis'8-2 r4 } cis,4-1 \tuplet 3/2 { e'8-2 r4 } |
    fis,,4-1 \tuplet 3/2 { d'8-2 r4 } gis,,4-1 \tuplet 3/2 { c'8-2 r4 } |
    cis,4-1 \tuplet 3/2 { cis'8-2 r4 } \tuplet 3/2 { cis'8-3 r4 } \tuplet 3/2 { cis'8-4 r4 } |
    \tuplet 3/2 { cis'8-2 r4 } fis,4-2 a,4-1 fis,4-2 |
    cis,4-5 \tuplet 3/2 { cis'8-2 r4 } \tuplet 3/2 { cis'8-3 r4 } \tuplet 3/2 { cis'8-4 r4 } |
    \tuplet 3/2 { cis'8-2 r4 } fis,4-2 a,4-1 fis,4-2 |
    cis,4-5 \tuplet 3/2 { cis'8-2 r4 } fis,,4-1 \tuplet 3/2 { cis'8-2 r4 } |
    dis,4-3 \tuplet 3/2 { b8-1 r4 } \tuplet 3/2 { b8-2 r4 } e,4-1 |
    cis,4-3 dis,4-2 c,4-4 cis,4-2 |
    a,,4-4 \tuplet 3/2 { fis8-2 r4 } gis,,4-2 fis,,4-4 |
    gis,,4-3 \tuplet 3/2 { gis8-2 r4 } gis,,4-1 \tuplet 3/2 { fis8-2 r4 } |
    cis,4-1 \tuplet 3/2 { gis8-2 r4 } \tuplet 3/2 { gis8-3 r4 } gis,8.-2 gis,16-2 |
    c,4-5 \tuplet 3/2 { gis8-2 r4 } \tuplet 3/2 { gis8-3 r4 } gis,8.-1 gis,16-1 |
    cis,2.-4 gis,8.-1 gis,16-2 |
    <gis,-1 gis,,-5>2. \tuplet 3/2 { gis,4-3 fis32-1 } gis,16-4 |
    <gis,-2 cis,-5>2. gis,8.-3 gis,16-2 |
    <gis,-1 gis,,-5>2. gis,8.-1 gis,16-1 |
    <gis,-1 cis,-4>2 cis2-2 |
    \tuplet 3/2 { gis,8-5 cis8-2 r4 } \tuplet 3/2 { e8-1 r8 } \tuplet 3/2 { gis,8-3 r8 gis,8-2 } \tuplet 3/2 { e,8-4 r8 e,8-1 } |
    cis,2-4 <gis,-1 cis,-4>2 |
    <gis,-1 cis,-4>1
}

\score {
<<
  \new PianoStaff <<
    \new Staff = "R" \staffA
    \new Staff = "L" \staffB
  >>
>>
  \layout { }
}
