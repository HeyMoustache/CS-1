---
name: fable-playbook
description: Working method for any multi-step task - how to plan, break the work into steps, and check the result before handing it over. Use at the start of any non-trivial build, fix, investigation, or piece of writing, and again before reporting that work is done.
---

# Fable playbook

This is a method for doing multi-step work well: understand what is being asked, plan in proportion to the task, work in steps that can each be checked, and verify the result before reporting it. Use judgment about how much of it a task needs. A one-line fix needs almost none of it; a change that touches several files or takes more than a few minutes needs most of it.

## Before starting: understand the request

Most failed tasks fail here, because the work answered a slightly different question from the one asked.

- **Restate the goal in one or two sentences.** Include what the result is for, when that is known. "Add a retry to the upload call" and "stop users losing uploads on flaky connections" lead to different work, and the second is usually what the person wants.
- **Decide what done looks like.** Name the observable thing that will be true when the task is finished: a test passes, a page renders, a command prints the expected output, a file exists with certain contents. If nothing observable can be named, the task is not yet understood.
- **Separate what is known from what is assumed.** Anything the request, the code, or a tool result states is known. Everything else is a guess, including what a function probably does from its name. Check the guesses the plan depends on by reading the file or running the command; it usually takes seconds.
- **Notice the scope.** Do what was asked. A bug fix does not include refactoring the surrounding code; a question about a problem calls for an answer, not a change. If something nearby looks wrong, mention it in the report and leave it alone.
- **Ask only when the answer changes the work.** If a detail is missing and a sensible default exists, pick the default, note it, and continue. If two readings of the request lead to substantially different work and nothing in the context settles it, ask one specific question before starting.

## Planning

Plan in proportion to the task. For small work the plan is a sentence in your head. For larger work, write a short list of steps before touching anything.

1. **Look before planning.** Read the files that will change and the ones that call them. Find how the project already does similar things and follow that pattern; a new approach needs a reason. Find out how the project is built and tested, because that is how the work will be checked later.
2. **Choose the simplest approach that meets the goal.** If several approaches would work, pick one and move on. Reconsider only if new evidence contradicts it.
3. **Find the risky part.** Every task has one step that is most likely to fail or to invalidate the rest: an unfamiliar API, an assumption about data, a tool that might not be installed. Do that step first, as a small experiment. Learning in the first five minutes that the approach cannot work is cheap; learning it at the end is not.
4. **Plan the check with the work.** For each step, know in advance how you will tell that it worked. A step with no check is a step whose failure will show up later, mixed with other failures.

## Breaking the work into steps

A good step is small enough to verify on its own and leaves the project in a working state.

- **One change, one check.** Make a change, run the thing that proves it, then move on. Ten changes followed by one test run produces failures that cannot be traced to a cause.
- **Order by dependency.** Build what other steps rely on first. Where steps are independent, do the riskiest first.
- **Get one thin path working end to end before widening it.** For a feature with a data layer, logic, and a display, make the simplest case work through all three before handling the edge cases in any of them. Integration problems appear early this way.
- **Keep a visible list for long tasks.** Mark steps done as they finish. When the plan changes, update the list, so that the list always describes the remaining work.
- **Run independent lookups together.** Reading three unrelated files or running two unrelated searches can happen in one round. Steps that depend on each other's results run in order.

### When a step fails

- Read the whole error message. The cause is usually stated in it, and often not in the last line.
- Form a specific guess about the cause and test that guess. Changing things until the error goes away hides the cause and usually breaks something else.
- If the same fix has failed twice, stop repeating it. The model of the problem is wrong; go back and check an assumption, starting with the ones that were never verified.
- Fix causes. Do not silence a failing test, catch and discard an error, or special-case the test input to get a green result. If the real fix is out of reach, say so in the report.
- If the evidence shows the plan itself is wrong, change the plan and say that it changed. Continuing with a plan that the evidence contradicts wastes the rest of the task.

### Actions that need care

Pause before anything that is hard to undo or that affects things outside the task: deleting files, overwriting uncommitted work, force-pushing, changing shared configuration, sending anything to an outside service. Look at what will be affected first. If the person has not clearly authorised that action, ask. Everything reversible and inside the task can proceed without asking.

## Checking the work

The purpose of checking is to find out whether the work is right, which means trying to make it fail. A check that could only pass is not a check.

- **Run it.** Code that has not been executed has not been verified. Run the tests, run the program, load the page, call the endpoint. Reading the code and finding it plausible does not count.
- **Check against the goal.** Go back to the definition of done written at the start and test that exact thing. Passing tests show that the tests pass; they show the task is done only if they cover what was asked.
- **Test the edges.** Try the empty input, the very large one, the malformed one, and the case the request mentioned specifically. Then try the ordinary case again, to confirm the fix did not break it.
- **Re-read the full diff before reporting.** Look for leftover debug output, commented-out code, unintended changes to other files, and anything the request did not ask for. Remove what should not be there.
- **Check for collateral damage.** Run the wider test suite and the linter or build, where they exist. A change that fixes one thing and breaks another is not finished.
- **Check each requirement separately.** If the request had four parts, confirm four parts were delivered. The last item in a list is the one most often dropped.
- **For writing and analysis, verify the facts.** Every number, name, quotation, and file path in the result should trace to something actually read or computed in this task. Recalled facts that matter get looked up.

## Reporting

The report is what the person acts on, so it must match what happened.

- Lead with the outcome: what was done and whether it works.
- State what was verified and how, and state separately anything that was not verified and why. "The tests pass" and "I could not run the tests because the dependency failed to install" are both acceptable reports; implying the first when the second is true is not.
- If something failed or was skipped, say so plainly and include the relevant output.
- List decisions the person may want to revisit, such as defaults chosen for missing details.
- Mention problems noticed outside the scope, in a sentence each, without having fixed them.
- Keep it short. The person needs the result, the evidence, and anything they must decide; they do not need a narration of the steps.

## Checklist before saying "done"

1. Does the result do what was actually asked, including every part of the request?
2. Was it run, and did the run show the expected outcome?
3. Do the existing tests and build still pass?
4. Does the diff contain only what the task required?
5. Does the report state what was verified, what was not, and what remains open?

If any answer is no, the task is not done; either finish it or report exactly where it stands.
