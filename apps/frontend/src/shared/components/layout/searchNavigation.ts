export function buildSearchResultDestination(
  repositoryId: string,
  result: { type: 'repository' | 'file'; path: string },
): string {
  const repositoryPath = `/repositories/${repositoryId}`;
  if (result.type === 'repository') return repositoryPath;

  const searchParams = new URLSearchParams({ tab: 'Explorer', path: result.path });
  return `${repositoryPath}?${searchParams.toString()}`;
}
