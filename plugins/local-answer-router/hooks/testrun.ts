import type { LastTest } from '../types'

const RUNNERS: readonly RegExp[] = [
  /^(?:pytest|py\.test)(?: |$)/,
  /^python3?(?:\.\d+)? -m (?:pytest|unittest)(?: |$)/,
  /^(?:npm|pnpm|yarn) (?:run )?test(?: |$)/,
  /^npm t(?: |$)/,
  /^cargo(?: \+\S+)? test(?: |$)/,
  /^go test(?: |$)/,
  /^dotnet test(?: |$)/,
  /^(?:mvn|\.\/mvnw) test(?: |$)/,
  /^(?:gradle|\.\/gradlew) test(?: |$)/,
  /^(?:bundle exec )?rspec(?: |$)/,
  /^(?:npx )?jest(?: |$)/,
  /^(?:npx )?vitest(?: |$)/,
  /^make test(?: |$)/,
]

// A runner named anywhere in a command, however it is wrapped: used only to notice that a test run
// happened which isTestCommand cannot read cleanly, so the older record must not keep answering.
const MENTIONS_RUNNER =
  /(?:^|[^A-Za-z0-9_.-])(?:pytest|py\.test|unittest|jest|vitest|rspec)(?![A-Za-z0-9_-])|(?:^|[^A-Za-z0-9_-])(?:npm|pnpm|yarn)\s+(?:run\s+)?t(?:est)?(?![A-Za-z0-9_-])|(?:cargo(?:\s+\+\S+)?|go|dotnet|mvn|\.\/mvnw|gradle|\.\/gradlew|make)\s+test(?![A-Za-z0-9_-])/

const ASSIGNMENTS = /^(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)+/
const CD = /^cd(?: |$)/
const MAX_COMMAND = 200

// These modes inspect the runner or collect/list tests; a zero exit code is not
// evidence that tests ran. Keep flags runner-specific so unrelated arguments
// (for example pytest -k listTests) do not turn a genuine run into an inspection.
const INSPECTION_MODES: readonly [RegExp, RegExp][] = [
  [/^(?:pytest|py\.test|python3?(?:\.\d+)? -m pytest)(?: |$)/, /(?:^|\s)--(?:collect-only|collectonly|co)(?:=|\s|$)/],
  [/^cargo(?: \+\S+)? test(?: |$)/, /(?:^|\s)--(?:no-run|list)(?:=|\s|$)/],
  [/^(?:npx )?jest(?: |$)/, /(?:^|\s)--(?:listTests|showConfig|clearCache)(?:=|\s|$)/],
  [/^go test(?: |$)/, /(?:^|\s)-list(?:=|\s|$)/],
  [/^dotnet test(?: |$)/, /(?:^|\s)--list-tests(?:=|\s|$)/],
]
const INFO_FLAG = /(?:^|\s)(?:--help|--version|-h|-V)(?:=|\s|$)/

// Fields of a Bash result that say the command did not run to its end in the foreground.
const NOT_FINISHED = ['backgroundTaskId', 'backgroundedByUser', 'timedOutAfterMs', 'interrupted'] as const

/**
 * True when the command's exit status is the test run's: runner last, only `cd` before it, and no
 * `;`, `|`, `&` or newline that would let another command decide the status. A wrong "passed"
 * answer is worse than none, so anything doubtful is not a test command.
 */
export const isTestCommand = (command: string): boolean => {
  const cleaned = command.replace(/\d*>&\d+/g, ' ').replace(/&&/g, '\u0000')
  if (/[;|&\r\n]/.test(cleaned)) {
    return false
  }
  const segments = cleaned.split('\u0000').map(segment => segment.trim())
  const last = segments[segments.length - 1].replace(ASSIGNMENTS, '')
  if (!RUNNERS.some(runner => runner.test(last))) {
    return false
  }
  const options = last.replace(/['"]/g, '')
  if (INFO_FLAG.test(options) || INSPECTION_MODES.some(([runner, flags]) => runner.test(last) && flags.test(options))) {
    return false
  }
  return segments.slice(0, -1).every(segment => CD.test(segment))
}

const finishedInForeground = (result: unknown): boolean => {
  if (typeof result !== 'object' || result === null) {
    return true
  }
  const fields = result as Record<string, unknown>
  return !NOT_FINISHED.some(key => Boolean(fields[key]))
}

/** What a finished Bash call means for the kept record of the last test run. */
export type Observation = { kind: 'record'; record: LastTest } | { kind: 'clear' } | { kind: 'ignore' }

/**
 * The rule is: record only when certain, otherwise clear. A clean foreground test command is
 * recorded (failed or not, whatever its output says). A test run that cannot be read cleanly
 * (piped, chained, backgrounded, interrupted) clears the record, so the question goes to the model
 * instead of an older run answering for it. Anything unrelated to tests changes nothing.
 */
export const observe = (
  command: string,
  background: boolean,
  ran: { deny?: string; isError?: boolean; result?: unknown },
  now: number,
): Observation => {
  if (ran.deny !== undefined) {
    return { kind: 'ignore' }
  }
  if (!isTestCommand(command)) {
    return MENTIONS_RUNNER.test(command) ? { kind: 'clear' } : { kind: 'ignore' }
  }
  if (background || !finishedInForeground(ran.result)) {
    return { kind: 'clear' }
  }
  return {
    kind: 'record',
    record: { command: command.trim().slice(0, MAX_COMMAND), failed: ran.isError === true, at: now },
  }
}
