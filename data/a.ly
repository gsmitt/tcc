\version "2.18.2"
\include "lilypond-book-preamble.ly"

\paper {
  indent = 2\mm
  line-width = 210\mm
}

\layout {
  indent = #0
  \context {
    \Score
    \remove "Bar_number_engraver"
  }
}

music = \relative c'
{
  r16[ g16 \tuplet 3/2 { r16 e'8] }
  g16( a \tuplet 3/2 { b d e') }

}

\score{
  \music
  \layout{}
  \midi{}
}