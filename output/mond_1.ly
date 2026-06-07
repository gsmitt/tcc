\version "2.26.0"

\paper {
  indent = 0\mm
  line-width = 180\mm
}

\header {
  tagline = ##f
}

right = {
  \clef treble
  \time 4/4
  \set fingeringOrientations = #'(up)
  \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } |
    \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } |
    \tuplet 3/2 { a8-1 cis'8-2 e'8-4 } \tuplet 3/2 { a8-1 cis'8-2 e'8-4 } \tuplet 3/2 { a8-1 d'8-2 fis'8-4 } \tuplet 3/2 { a8-1 d'8-2 fis'8-4 } |
    \tuplet 3/2 { gis8-1 c'8-2 fis'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 dis'8-4 } \tuplet 3/2 { fis8-1 c'8-4 dis'8-1 } |
    \tuplet 3/2 { e8-1 gis8-2 cis'8-5 } \tuplet 3/2 { gis8-2 cis'8-3 e'8-5 } \tuplet 3/2 { gis8-1 cis'8-3 e'8-5 } \tuplet 3/2 { <gis-1 gis'-5>8 cis'8-2 e'32-3 } gis'16-5 |
    \tuplet 3/2 { <gis-1 gis'-5>8 dis'8-3 fis'8-4 } \tuplet 3/2 { gis8-1 dis'8-3 fis'8-4 } \tuplet 3/2 { gis8-1 dis'8-3 fis'8-4 } \tuplet 3/2 { <gis-1 gis'-5>8 dis'8-2 fis'32-3 } gis'16-4 |
    \tuplet 3/2 { <gis-1 gis'-5>8 cis'8-2 e'8-4 } \tuplet 3/2 { gis8-1 cis'8-2 e'8-4 } \tuplet 3/2 { <a-1 a'-5>8 cis'8-2 fis'8-4 } \tuplet 3/2 { r4 fis'8-2 } |
    \tuplet 3/2 { gis'4-3 e'8-1 } \tuplet 3/2 { r4 e'8-2 } \tuplet 3/2 { fis'4-3 dis'8-2 } \tuplet 3/2 { b'4-5 dis'8-2 } |
    \tuplet 3/2 { e'8..-3~ e'64. }
}

left = {
  \clef bass
  \time 4/4
  \set fingeringOrientations = #'(down)
  <cis-1 cis,-5>1 |
    <b,-1 b,,-5>1 |
    <a,-1 a,,-5>2 <fis,-1 fis,,-5>2 |
    <gis,-1 gis,,-5>2 <gis,-1 gis,,-5>2 |
    <cis-1 gis,-2 cis,-5>1 |
    <c-1 gis,-2 c,-5>1 |
    <cis-1 cis,-5>2 <fis,-1 fis,,-5>4 \tuplet 3/2 { a8-4 cis'8-2 r8 } |
    \tuplet 3/2 { <gis-1 b,-4 b,,-5>8 b8-1 r8 } \tuplet 3/2 { gis8-2 b8-1 r8 } \tuplet 3/2 { <a-1 b,-4 b,,-5>8 b8-2 r8 } \tuplet 3/2 { a8-3 b8-1 r8 } |
    \tuplet 3/2 { <gis-2 e-4 e,-5>8 b8-1 }
}

\score {
  \new PianoStaff <<
    \new Staff = "RH" \right
    \new Staff = "LH" \left
  >>
  \layout { }
}
