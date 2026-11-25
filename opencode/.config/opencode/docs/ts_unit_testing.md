# Unit testing in TypeScript, Nuxt, Vue 3 - Best Practices & Conventions for all work.

## Unit testing

- Tests are written using Vitest, Nuxt Test Utils, Vue Test Utils, Happy Dom, V8 Coverage.
- Always include a smoke test as the first test in a new test file, to ensure the test setup is working correctly.
  eg.

```ts
it("renders OK", async () => {
  // Arrange
  const props: MyProps = {
    data: [],
  };

  // Act
  const wrapper = await shallowMount(component, {
    props,
  });

  // Assert
  expect(wrapper.exists()).toBe(true);
});
```

- Run the smoke test first to ensure the test setup is working correctly, before writing more specific tests.
- Aim for ~90% test coverage on any code included in the test suite, but don't write unnecessary tests
- Use the Arrange - Act - Assert pattern for writing tests, where possible. This helps to structure the tests and make them easier to read and understand.
- Test the ins and outs of a component, but don't test implementation details. Focus on testing the public API and expected behaviour, rather than the internal workings of the component.
- When writing tests, consider edge cases and potential failure points, but don't over-engineer tests
- If writing a test exposes a bug in the code, report the bug to the user (me) and ask whether to fix it. Usually the scope of writing tests does not include working on the app itself, but I will judge this.
- Clean up mocks to prevent test data leakage.
- Add `data-test` attributes to component templates to make targeting elements easy in tests and to prevent test breakage if other selectors such as class names are changed.
- If you need to create a lot of test data, it helps to use factory functions or to create separate files with the test data to import.
- Avoid using timeouts and other delaying tactics in tests, they will cause the entire test suite to become very slow to run. Using async - await, or `await nextTick()` is fine though.
- Comments are very useful in tests, they can serve as documentation for the component itself.
- IMPORTANT - Never write a test that tests itself. Tests must test actual code, this would be unacceptable:
  ```ts
  const variable = 10;
  expect(variable).toEqual(10);
  ```
- Sometimes components can be extremely difficult to test due to use of browser APIs, or other dependencies. First try to mock/stub all of the problematic parts, and if it is still too difficult, we may exclude this part of the file from coverage, but report back.
- Tests should only test one thing - the one component or function being tested. All child components and other dependencies may be stubbed/mocked.
- Tests should use only enough types to avoid type errors or use of `any`, otherwise inferred types are fine.
