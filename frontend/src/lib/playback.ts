/**
 * How often a player says where it has got to, and when the board's answer is
 * an instruction rather than an echo of its own last tick.
 *
 * A four-hour film cannot report every frame: `timeupdate` fires several times a
 * second, and every report here is a write on the server and a broadcast to
 * every other browser looking at the board. Ten seconds costs nothing and loses
 * at most ten seconds across a reload, which is the whole of what this buys.
 *
 * That lag is why a position coming back from the board is not simply obeyed.
 * The board is always a little behind whatever is actually playing, so a player
 * moves only when the difference is bigger than the lag can explain — and a
 * session asking for the third hour of something always is. Without that, every
 * tick would come round through the server and jog the film it just reported.
 *
 * Shared by the file player and YouTube's, which have the same problem and no
 * business disagreeing about the answer.
 */

/** How often a playing widget reports where it is. */
export const TICK_SECONDS = 10;

/** How far the board must be from a player before the player goes there. */
export const APART_SECONDS = 20;

/**
 * How often YouTube's player is asked where it is.
 *
 * A `<video>` says so by itself; YouTube's player only answers when asked, and
 * the answer has to be fresher than the tick that reports it.
 */
export const ASK_SECONDS = 2;
